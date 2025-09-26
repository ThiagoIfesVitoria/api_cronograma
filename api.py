import pandas as pd
import json
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import io
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List


# Importe as suas funções refatoradas
from criar_sessoes import criar_sessoes
from criar_matriz import criar_matriz
from otimizador import otimizar_cronograma

# Inicializa a aplicação FastAPI
app = FastAPI()

# --- Configuração do CORS ---
# Isto é ESSENCIAL para permitir que seu frontend (rodando em localhost:3000)
# se comunique com seu backend (rodando em localhost:8000).
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NOVO ENDPOINT PARA OBTER NOMES DAS ABAS ---
@app.post("/api/obter-nomes-abas")
async def obter_nomes_abas_endpoint(arquivo: UploadFile = File(...)):
    """
    Recebe um arquivo Excel e retorna uma lista com os nomes de todas as suas abas (sheets).
    """
    try:
        # Lê o conteúdo do arquivo enviado para a memória
        contents = await arquivo.read()
        # Usa o Pandas para ler os nomes das abas sem carregar os dados de cada uma
        excel_file = pd.ExcelFile(contents)
        return excel_file.sheet_names
    except Exception as e:
        # Se o arquivo não for um Excel válido ou estiver corrompido, retorna um erro
        raise HTTPException(
            status_code=400,
            detail=f"Não foi possível processar o arquivo. Verifique se é um arquivo Excel (.xlsx) válido. Erro: {e}"
        )

# --- Criação do Endpoint da API ---
@app.post("/api/gerar-cronograma")
async def gerar_cronograma_endpoint(
    # Parâmetros recebidos do formulário do Next.js
    data_inicio_str: str = Form(...),
    data_fim_str: str = Form(...),
    dias_da_semana_json: str = Form(...), # Dias virão como uma string JSON
    horarios_inicio_list_str: str = Form(...), # Horários como string separada por vírgula
    duracao_sessao_horas: int = Form(...),
    capacidade_padrao: int = Form(...),
    equipes_str: str = Form(...), # Equipes como string separada por vírgula
    arquivo: UploadFile = File(...)
):
    

    try:
        # --- ETAPA 0: Processar os inputs recebidos ---
        # Converte as strings recebidas para os formatos corretos
        dias_da_semana = json.loads(dias_da_semana_json)
        horarios_inicio_list = [h.strip() for h in horarios_inicio_list_str.split(',')]
        equipes_para_processar = [e.strip() for e in equipes_str.split(',')]

        # --- ETAPA 1: Gerar Sessões ---
        df_sessoes = criar_sessoes(
            data_inicio_str, data_fim_str, dias_da_semana, horarios_inicio_list,
            duracao_sessao_horas, capacidade_padrao
        )
        if not isinstance(df_sessoes, pd.DataFrame) or df_sessoes.empty:
            raise HTTPException(status_code=400, detail="Nenhuma sessão pôde ser gerada com os parâmetros fornecidos.")

        # --- ETAPA 2: Criar Matriz ---
        # Para usar a função criar_matriz que espera um caminho de arquivo,
        # salvamos o arquivo enviado temporariamente.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(await arquivo.read())
            temp_file_path = temp_file.name

        df_matriz = criar_matriz(df_sessoes, equipes_para_processar, temp_file_path)
        
        # Remove o arquivo temporário após o uso
        os.unlink(temp_file_path)

        if df_matriz.empty:
            raise HTTPException(status_code=400, detail="Matriz de disponibilidade não pôde ser criada. Verifique o arquivo Excel e os nomes das equipes.")

        # --- ETAPA 3: Otimizar Cronograma ---
        resultado = otimizar_cronograma(df_sessoes, df_matriz)
        if not resultado or resultado.get("status") != 'Optimal':
             raise HTTPException(status_code=500, detail=f"Otimização falhou ou não encontrou solução. Status: {resultado.get('status')}")

        return resultado

    except Exception as e:
        # Captura qualquer erro inesperado e retorna uma resposta clara
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {str(e)}")
    
# --- Modelos Pydantic para validar os dados do relatório ---
# Isso garante que o JSON enviado pelo frontend tem a forma que esperamos.

class SessaoAgendada(BaseModel):
    nome_sessao: str
    data_evento: str
    hora_inicio: str
    hora_fim: str
    quantidade_pessoas: int
    integrantes: List[str]

class ResultadoRelatorio(BaseModel):
    total_sessoes_utilizadas: int
    sessoes_agendadas: List[SessaoAgendada]


@app.post("/api/criar-relatorio-excel")
async def criar_relatorio_excel_endpoint(resultado: ResultadoRelatorio):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # --- 1. DEFINIÇÃO DOS ESTILOS (FORMATOS) ---
        title_format = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#002D5B', 'valign': 'vcenter'})
        header_format = workbook.add_format({'bold': True, 'fg_color': '#002D5B', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_format = workbook.add_format({'border': 1})
        bold_format = workbook.add_format({'bold': True})

        # --- 2. CRIAÇÃO DA ABA DE RESUMO GERAL ---
        resumo_data = []
        for s in resultado.sessoes_agendadas:
            resumo_data.append({
                'Sessão': s.nome_sessao,
                'Data': pd.to_datetime(s.data_evento).strftime('%d/%m/%Y'),
                'Horário': f"{s.hora_inicio} - {s.hora_fim}",
                'Nº de Participantes': s.quantidade_pessoas
            })
        
        df_resumo = pd.DataFrame(resumo_data)
        df_resumo.to_excel(writer, sheet_name='Resumo_Geral', startrow=2, index=False)
        
        # Formatando a aba de resumo
        resumo_sheet = writer.sheets['Resumo_Geral']
        resumo_sheet.write('A1', 'Resumo do Cronograma Otimizado', title_format)
        
        # Aplicando formato de cabeçalho na tabela de resumo
        for col_num, value in enumerate(df_resumo.columns.values):
            resumo_sheet.write(2, col_num, value, header_format)
            
        # Autoajuste da largura das colunas na aba de resumo
        for i, col in enumerate(df_resumo.columns):
            column_len = max(df_resumo[col].astype(str).str.len().max(), len(col)) + 2
            resumo_sheet.set_column(i, i, column_len)

        # --- 3. CRIAÇÃO DAS ABAS DETALHADAS PARA CADA SESSÃO ---
        for sessao in resultado.sessoes_agendadas:
            sheet_name = sessao.nome_sessao.replace(" ", "_")[:31]
            df_participantes = pd.DataFrame({'Integrantes da Sessão': sorted(sessao.integrantes)})
            
            df_participantes.to_excel(writer, sheet_name=sheet_name, startrow=5, index=False)
            
            worksheet = writer.sheets[sheet_name]
            
            # Escrevendo o cabeçalho de informações da sessão
            worksheet.write('A1', f"Detalhes da {sessao.nome_sessao}", title_format)
            worksheet.write('A3', 'Data:', bold_format)
            worksheet.write('B3', pd.to_datetime(sessao.data_evento).strftime('%d/%m/%Y'))
            worksheet.write('A4', 'Horário:', bold_format)
            worksheet.write('B4', f"{sessao.hora_inicio} - {sessao.hora_fim}")
            worksheet.write('D3', 'Total de Participantes:', bold_format)
            worksheet.write('E3', sessao.quantidade_pessoas)
            
            # Formatando a tabela de participantes
            worksheet.write(5, 0, 'Integrantes da Sessão', header_format)
            worksheet.set_column('A:A', 40) # Ajusta a largura da coluna de nomes

    output.seek(0)
    headers = {'Content-Disposition': 'attachment; filename="cronograma_otimizado.xlsx"'}
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
