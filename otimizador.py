# otimizador.py
import pulp
import pandas as pd

def otimizar_cronograma(df_sessoes, df_matriz_disponibilidade):
    """
    Executa o modelo de otimização para encontrar o cronograma ideal.

    Args:
        df_sessoes (pd.DataFrame): DataFrame com os detalhes de todas as sessões possíveis.
        df_matriz_disponibilidade (pd.DataFrame): Matriz binária de disponibilidade.

    Returns:
        dict: Um dicionário com o status da solução e o cronograma final,
              pronto para ser convertido para JSON. Retorna None se não houver solução.
    """
    pessoas = df_matriz_disponibilidade.columns.to_list()
    sessoes_nomes = df_matriz_disponibilidade.index.to_list()

    dict_sessao = {}
    for index, row in df_sessoes.iterrows():
        dict_sessao[row['Sessao']] = {'capacidade': row['Capacidade'], 'mes': row['Mês do evento']}
    
    sessoes = dict_sessao
    disponibilidade = df_matriz_disponibilidade.T.to_dict(orient='index')

    problema = pulp.LpProblem("Cronograma_Otimizado", pulp.LpMinimize)

    x = pulp.LpVariable.dicts("alocacao", ((p, s) for p in pessoas for s in sessoes_nomes), cat='Binary')
    y = pulp.LpVariable.dicts("sessao_utilizada", sessoes_nomes, cat='Binary')

    problema += pulp.lpSum([y[s] for s in sessoes_nomes]), "Numero_de_Sessoes_Utilizadas"

    # --- Restrições ---
    for p in pessoas:
        for s in sessoes_nomes:
            problema += x[p, s] <= disponibilidade[p][s], f"Disponibilidade_{p}_{s}"

    for p in pessoas:
        problema += pulp.lpSum([x[p, s] for s in sessoes_nomes]) == 1, f"Uma_Sessao_Por_Pessoa_{p}"

    for s in sessoes_nomes:
        problema += pulp.lpSum([x[p, s] for p in pessoas]) <= sessoes[s]['capacidade'] * y[s], f"Capacidade_Sessao_{s}"

    meses = sorted(list(set(s['mes'] for s in sessoes.values())))
    for m in meses:
        sessoes_do_mes = [s for s, dados in sessoes.items() if dados['mes'] == m]
        problema += pulp.lpSum([y[s] for s in sessoes_do_mes]) <= 2, f"Maximo_2_Sessoes_por_Mes_{m}"


    # # cplex
    # cplex_path = r"C:\Program Files\IBM\ILOG\CPLEX_Studio_Community2212\cplex\bin\x64_win64\cplex.exe"
    
    # # Passe o caminho para o PuLP
    # solver_cplex = pulp.CPLEX_CMD(path=cplex_path)
    # problema.solve(solver_cplex)

    # normal
    problema.solve(pulp.PULP_CBC_CMD(timeLimit=1000, gapRel=0.02))

    if pulp.LpStatus[problema.status] != 'Optimal':
        return {
            "status": pulp.LpStatus[problema.status],
            "sessoes_agendadas": []
        }

    # --- Montagem do resultado em formato de dicionário ---
    resultado_final = {
        "status": pulp.LpStatus[problema.status],
        "total_sessoes_utilizadas": int(pulp.value(problema.objective)),
        "sessoes_agendadas": []
    }

    for sessao_nome in sessoes_nomes:
        if y[sessao_nome].varValue == 1:
            pessoas_agendadas = [p for p in pessoas if x[p, sessao_nome].varValue == 1]
            
            sessao_info = df_sessoes.loc[df_sessoes['Sessao'] == sessao_nome].iloc[0]

            resultado_final["sessoes_agendadas"].append({
                "nome_sessao": sessao_nome,
                "data_evento": sessao_info['Data do evento'],
                "hora_inicio": sessao_info['Hora ini'],
                "hora_fim": sessao_info['Hora fim'],
                "quantidade_pessoas": len(pessoas_agendadas),
                "integrantes": pessoas_agendadas
            })
            
    return resultado_final