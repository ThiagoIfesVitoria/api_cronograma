import pandas as pd

def criar_matriz(df_sessoes, list_equipes, caminho_arquivo):
    """
    Cria a matriz de disponibilidade.
    Lê as abas de um arquivo Excel especificadas em 'list_equipes',
    processa a disponibilidade e a cruza com o dataframe de sessões.

    Args:
        df_sessoes (pd.DataFrame): DataFrame com todas as sessões possíveis.
        list_equipes (list): Lista de strings com os nomes das equipes (abas do Excel) a serem processadas.
        caminho_arquivo (str): O caminho para o arquivo Excel de disponibilidade.

    Returns:
        pd.DataFrame: A matriz de disponibilidade binária.
    """
    # --- 1. Leitura e consolidação dos dados de disponibilidade ---
    dataframes_equipes = []

    # Estrutura de repetição para abrir e carregar apenas as abas das equipes que estão no list_equipes.
    try:
        for equip in list_equipes:
            df_equipe = pd.read_excel(caminho_arquivo, sheet_name=equip, skiprows=1)

            # Separa os dataframes que estão na mesma aba
            dfdisp = df_equipe[["Data","Turma","hora ini","hora fim"]].dropna(subset=["Data"])
            dfresp = df_equipe[["Nome","Turma.1"]].rename(columns={"Turma.1": 'Turma'}).dropna(subset=['Nome'])

            df_desnormalizado = pd.merge(dfdisp, dfresp, on='Turma', how='inner')
            df_desnormalizado = df_desnormalizado[['Data', 'hora ini', 'hora fim', 'Nome', 'Turma']]
            dataframes_equipes.append(df_desnormalizado)
    except FileNotFoundError:
        print(f"Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao ler a aba '{equip}' do arquivo Excel. Verifique se o nome e o formato estão corretos. Detalhe: {e}")
        return pd.DataFrame()

    if not dataframes_equipes:
        print("Erro: Nenhuma aba válida encontrada ou processada para as equipes fornecidas.")
        return pd.DataFrame()

    # Concatena todos os DataFrames da lista em um único chamado df_disponibilidade_bruta
    df_disponibilidade_bruta = pd.concat(dataframes_equipes, ignore_index=True)

    # --- 2. Preparação e processamento dos dados ---
    df_disponibilidade_bruta['Inicio_Disp'] = pd.to_datetime(
        df_disponibilidade_bruta['Data'].astype(str) + ' ' + df_disponibilidade_bruta['hora ini'].astype(str)
    )
    df_disponibilidade_bruta['Fim_Disp'] = pd.to_datetime(
        df_disponibilidade_bruta['Data'].astype(str) + ' ' + df_disponibilidade_bruta['hora fim'].astype(str)
    )

    df_sessoes['Inicio_Sessao'] = pd.to_datetime(
        df_sessoes['Data do evento'].astype(str) + ' ' + df_sessoes['Hora ini'].astype(str)
    )
    df_sessoes['Fim_Sessao'] = pd.to_datetime(
        df_sessoes['Data do evento'].astype(str) + ' ' + df_sessoes['Hora fim'].astype(str)
    )

    pessoas = df_disponibilidade_bruta['Nome'].unique()
    sessoes = df_sessoes['Sessao'].unique()

    # --- 3. Geração da matriz de disponibilidade ---
    df_matriz_disponibilidade = pd.DataFrame(0, index=sessoes, columns=pessoas)
    print("Processando a matriz de disponibilidade...")
    # ... (o resto do código de iteração e comparação de horários permanece exatamente o mesmo) ...
    for sessao_nome in sessoes:
        sessao_info = df_sessoes.loc[df_sessoes['Sessao'] == sessao_nome].iloc[0]
        inicio_sessao = sessao_info['Inicio_Sessao']
        fim_sessao = sessao_info['Fim_Sessao']

        for pessoa_nome in pessoas:
            disponibilidade_pessoa = df_disponibilidade_bruta[df_disponibilidade_bruta['Nome'] == pessoa_nome]
            disponivel = False
            for _, disp_row in disponibilidade_pessoa.iterrows():
                inicio_disp = disp_row['Inicio_Disp']
                fim_disp = disp_row['Fim_Disp']
                # Condição de contenção: a sessão deve estar DENTRO da disponibilidade
                if inicio_disp <= inicio_sessao and fim_sessao <= fim_disp:
                    disponivel = True
                    break
            if disponivel:
                df_matriz_disponibilidade.loc[sessao_nome, pessoa_nome] = 1

    return df_matriz_disponibilidade