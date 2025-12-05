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

# --- ENDPOINT PARA OBTER NOMES DAS ABAS ---
@app.post("/api/obter-nomes-abas")
async def obter_nomes_abas_endpoint(arquivo: UploadFile = File(...)):
    try:
        contents = await arquivo.read()
        excel_file = pd.ExcelFile(contents)
        return excel_file.sheet_names
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Não foi possível processar o arquivo. Verifique se é um arquivo Excel (.xlsx) válido. Erro: {e}"
        )

# --- ENDPOINT PRINCIPAL PARA GERAR O CRONOGRAMA ---
@app.post("/api/gerar-cronograma")
async def gerar_cronograma_endpoint(
    data_inicio_str: str = Form(...),
    data_fim_str: str = Form(...),
    dias_da_semana_json: str = Form(...),
    horarios_inicio_list_str: str = Form(...),
    duracao_sessao_horas: int = Form(...),
    capacidade_padrao: int = Form(...),
    equipes_str: str = Form(...),
    arquivo: UploadFile = File(...)
):
    try:
        
        # --- ETAPA 0: Processar os inputs recebidos ---
        dias_da_semana = json.loads(dias_da_semana_json)
        horarios_inicio_list = [h.strip() for h in horarios_inicio_list_str.split(',')]
        equipes_para_processar = [e.strip() for e in equipes_str.split(',')]
        # --- PASSO 1 DE DEPURAÇÃO: Imprimir os valores recebidos ---
        print("-----------------------------------------")
        print(f"DEBUG: Dias da semana recebidos do frontend (padrão Pandas esperado): {dias_da_semana}")
        print("-----------------------------------------")
        # -----------------------------------------

        # --- ETAPA 1: Gerar Sessões ---
        df_sessoes = criar_sessoes(
            data_inicio_str, data_fim_str, dias_da_semana, horarios_inicio_list,
            duracao_sessao_horas, capacidade_padrao
        )
        if not isinstance(df_sessoes, pd.DataFrame) or df_sessoes.empty:
            raise HTTPException(status_code=400, detail="Nenhuma sessão pôde ser gerada com os parâmetros fornecidos.")

        # --- ETAPA 2: Criar Matriz ---
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(await arquivo.read())
            temp_file_path = temp_file.name

        df_matriz = criar_matriz(df_sessoes, equipes_para_processar, temp_file_path)
        os.unlink(temp_file_path)

        if df_matriz.empty:
            raise HTTPException(status_code=400, detail="Matriz de disponibilidade não pôde ser criada. Verifique o arquivo Excel e os nomes das equipes.")

        # --- ETAPA 3: Otimizar Cronograma ---
        # A função otimizador_cronograma agora trata os seus próprios erros.
        # A verificação de 'status' foi removida porque já não é necessária.
        resultado = otimizar_cronograma(df_sessoes, df_matriz)
        
        # Se a otimização devolver um resultado vazio, informamos o utilizador.
        if not resultado:
             raise HTTPException(status_code=500, detail="A otimização retornou um resultado vazio.")

        return resultado

    except ValueError as ve:
        # Captura o erro específico que criámos no otimizador
        raise HTTPException(status_code=500, detail=f"Erro na otimização: {str(ve)}")
    except Exception as e:
        # Captura qualquer outro erro inesperado
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {str(e)}")
    
# --- Modelos Pydantic para validar os dados do relatório ---
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
    pessoas_nao_alocadas: List[str] = [] # Adicionado para corresponder ao novo resultado


@app.post("/api/criar-relatorio-excel")
async def criar_relatorio_excel_endpoint(resultado: ResultadoRelatorio):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        title_format = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#002D5B', 'valign': 'vcenter'})
        header_format = workbook.add_format({'bold': True, 'fg_color': '#002D5B', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        bold_format = workbook.add_format({'bold': True})
        alert_header_format = workbook.add_format({'bold': True, 'fg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

        # --- ABA DE RESUMO GERAL ---
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
        
        resumo_sheet = writer.sheets['Resumo_Geral']
        resumo_sheet.write('A1', 'Resumo do Cronograma Otimizado', title_format)
        
        for col_num, value in enumerate(df_resumo.columns.values):
            resumo_sheet.write(2, col_num, value, header_format)
            
        for i, col in enumerate(df_resumo.columns):
            column_len = max(df_resumo[col].astype(str).str.len().max(), len(col)) + 2
            resumo_sheet.set_column(i, i, column_len)

        # --- ADICIONA A LISTA DE NÃO ALOCADOS AO RESUMO ---
        if resultado.pessoas_nao_alocadas:
            start_row = len(df_resumo) + 6
            resumo_sheet.write(start_row, 0, 'Pessoas Não Alocadas', alert_header_format)
            df_nao_alocados = pd.DataFrame({'Nome': resultado.pessoas_nao_alocadas})
            df_nao_alocados.to_excel(writer, sheet_name='Resumo_Geral', startrow=start_row + 1, index=False, header=False)
            resumo_sheet.set_column(0, 0, 40)


        # --- ABAS DETALHADAS PARA CADA SESSÃO ---
        for sessao in resultado.sessoes_agendadas:
            sheet_name = sessao.nome_sessao.replace(" ", "_").replace(":", "-")[:31]
            df_participantes = pd.DataFrame({'Integrantes da Sessão': sorted(sessao.integrantes)})
            
            df_participantes.to_excel(writer, sheet_name=sheet_name, startrow=5, index=False)
            
            worksheet = writer.sheets[sheet_name]
            
            worksheet.write('A1', f"Detalhes da {sessao.nome_sessao}", title_format)
            worksheet.write('A3', 'Data:', bold_format)
            worksheet.write('B3', pd.to_datetime(sessao.data_evento).strftime('%d/%m/%Y'))
            worksheet.write('A4', 'Horário:', bold_format)
            worksheet.write('B4', f"{sessao.hora_inicio} - {sessao.hora_fim}")
            worksheet.write('D3', 'Total de Participantes:', bold_format)
            worksheet.write('E3', sessao.quantidade_pessoas)
            
            worksheet.write(5, 0, 'Integrantes da Sessão', header_format)
            worksheet.set_column('A:A', 40)

    output.seek(0)
    headers = {'Content-Disposition': 'attachment; filename="cronograma_otimizado.xlsx"'}
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
