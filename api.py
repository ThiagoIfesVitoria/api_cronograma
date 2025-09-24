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


# --- NOVO ENDPOINT PARA CRIAR E BAIXAR O RELATÓRIO EXCEL ---
@app.post("/api/criar-relatorio-excel")
async def criar_relatorio_excel_endpoint(resultado: ResultadoRelatorio):
    """
    Recebe os dados do cronograma em JSON e gera um relatório Excel formatado.
    """
    output = io.BytesIO()

    # Inicia o "escritor" de Excel usando o XlsxWriter como motor
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # --- Define os Estilos e Formatos ---
        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top',
            'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1
        })
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_color': '#4F81BD'
        })
        info_label_format = workbook.add_format({'bold': True, 'font_color': '#333333'})
        info_value_format = workbook.add_format({'font_color': '#333333'})

        # --- Cria uma aba para cada sessão ---
        for sessao in resultado.sessoes_agendadas:
            sheet_name = sessao.nome_sessao.replace(" ", "_")[:31] # Nomes de abas têm limite de 31 caracteres
            
            # Cria um DataFrame com os participantes
            df_participantes = pd.DataFrame({'Integrantes': sorted(sessao.integrantes)})
            
            # Escreve o DataFrame na aba, começando mais abaixo para dar espaço ao cabeçalho
            df_participantes.to_excel(writer, sheet_name=sheet_name, startrow=6, index=False)
            
            worksheet = writer.sheets[sheet_name]

            # --- Escreve o Cabeçalho com Informações da Sessão ---
            worksheet.write('B2', 'Relatório de Sessão', title_format)
            worksheet.write('B4', 'Data:', info_label_format)
            worksheet.write('C4', sessao.data_evento, info_value_format)
            worksheet.write('B5', 'Horário:', info_label_format)
            worksheet.write('C5', f"{sessao.hora_inicio} - {sessao.hora_fim}", info_value_format)
            worksheet.write('E4', 'Total de Participantes:', info_label_format)
            worksheet.write('F4', sessao.quantidade_pessoas, info_value_format)

            # --- Formata a Tabela de Participantes ---
            # Aplica o formato de cabeçalho à tabela
            for col_num, value in enumerate(df_participantes.columns.values):
                worksheet.write(6, col_num, value, header_format)
            
            # Ajusta a largura da coluna para melhor visualização
            worksheet.set_column('A:A', 40) # Coluna de Integrantes
            worksheet.set_column('B:F', 20) # Colunas de informações

    # Prepara o arquivo em memória para ser enviado
    output.seek(0)

    # Define os cabeçalhos para o navegador entender que é um arquivo para download
    headers = {
        'Content-Disposition': 'attachment; filename="cronograma_otimizado.xlsx"'
    }
    
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')