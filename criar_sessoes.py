import pandas as pd
from datetime import timedelta

def criar_sessoes(data_inicio_str, data_fim_str, dias_da_semana, horarios_inicio_list, duracao_sessao_horas, capacidade_padrao):
    """
    Cria um DataFrame com todas as sessões possíveis,
    já incluindo colunas de datetime para início e fim.
    """
    try:
        # 1. Gerar o range de datas
        df_datas = pd.DataFrame(pd.date_range(start=data_inicio_str, end=data_fim_str), columns=['Data do evento'])
        df_datas['Dia_Semana'] = df_datas['Data do evento'].dt.dayofweek
        
        # 2. Filtrar pelos dias da semana selecionados
        df_datas_filtrado = df_datas[df_datas['Dia_Semana'].isin(dias_da_semana)].copy()

        if df_datas_filtrado.empty:
            print("Nenhuma data válida encontrada para os dias da semana selecionados.")
            return pd.DataFrame()

        # 3. Processar horários
        horarios_processados = []
        for h in horarios_inicio_list:
            try:
                hora_inicio = pd.to_datetime(h).time()
                hora_fim = (pd.to_datetime(h) + timedelta(hours=duracao_sessao_horas)).time()
                horarios_processados.append({'Hora ini': hora_inicio, 'Hora fim': hora_fim})
            except Exception as e:
                print(f"Ignorando horário mal formatado: {h}. Erro: {e}")
                continue
        
        if not horarios_processados:
            print("Nenhum horário válido foi processado.")
            return pd.DataFrame()

        df_horarios = pd.DataFrame(horarios_processados)

        # 4. Cruzar datas e horários para criar sessões
        df_datas_filtrado['key'] = 1
        df_horarios['key'] = 1
        df_sessoes = pd.merge(df_datas_filtrado, df_horarios, on='key').drop('key', axis=1)

        if df_sessoes.empty:
            print("Nenhuma sessão foi criada a partir do cruzamento de datas e horários.")
            return pd.DataFrame()

        # 5. Adicionar informações restantes
        df_sessoes['Sessao'] = [f"sessao_{i+1}" for i in range(len(df_sessoes))]
        df_sessoes['Capacidade'] = capacidade_padrao

        # --- ALTERAÇÃO IMPORTANTE: Adicionar colunas de datetime ---
        df_sessoes['Inicio_Sessao'] = pd.to_datetime(
            df_sessoes['Data do evento'].astype(str) + ' ' + df_sessoes['Hora ini'].astype(str)
        )
        df_sessoes['Fim_Sessao'] = pd.to_datetime(
            df_sessoes['Data do evento'].astype(str) + ' ' + df_sessoes['Hora fim'].astype(str)
        )
        # --------------------------------------------------------

        # 6. Reordenar colunas
        colunas_finais = [
            'Sessao', 'Data do evento', 'Dia_Semana', 'Hora ini', 'Hora fim', 
            'Inicio_Sessao', 'Fim_Sessao', 'Capacidade'
        ]
        df_sessoes = df_sessoes[colunas_finais]

        return df_sessoes

    except Exception as e:
        print(f"Erro inesperado em criar_sessoes: {e}")
        return pd.DataFrame()