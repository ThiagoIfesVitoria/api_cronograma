# otimizador.py

import pandas as pd
import pulp

def otimizar_cronograma(df_sessoes, df_matriz, tempo_limite_segundos=120):
    """
    Função principal de otimização.
    Agora inclui variáveis de penalidade para pessoas não alocadas e um limite de tempo.
    """
    sessoes = df_matriz.index.tolist()
    pessoas = df_matriz.columns.tolist()

    problema = pulp.LpProblem("Alocacao_de_Pessoas", pulp.LpMinimize)

    x = pulp.LpVariable.dicts("Alocacao", (pessoas, sessoes), 0, 1, pulp.LpBinary)
    y = pulp.LpVariable.dicts("SessaoUtilizada", sessoes, 0, 1, pulp.LpBinary)
    nao_alocado = pulp.LpVariable.dicts("NaoAlocado", pessoas, 0, 1, pulp.LpBinary)

    penalidade_nao_alocar = len(pessoas) + 1
    problema += pulp.lpSum(y[s] for s in sessoes) + penalidade_nao_alocar * pulp.lpSum(nao_alocado[p] for p in pessoas)

    for s in sessoes:
        capacidade = df_sessoes.loc[df_sessoes['Sessao'] == s, 'Capacidade'].iloc[0]
        problema += pulp.lpSum(x[p][s] for p in pessoas) <= capacidade * y[s]

    for s in sessoes:
        problema += pulp.lpSum(x[p][s] for p in pessoas) >= 1 * y[s]

    for p in pessoas:
        for s in sessoes:
            if df_matriz.loc[s, p] == 0:
                problema += x[p][s] == 0

    for p in pessoas:
        problema += pulp.lpSum(x[p][s] for s in sessoes) + nao_alocado[p] == 1

    print(f"Iniciando otimização com limite de tempo de {tempo_limite_segundos} segundos...")
    #solver = pulp.PULP_CBC_CMD(timeLimit=tempo_limite_segundos)
    problema.solve()
    
    status_text = pulp.LpStatus.get(problema.status, "Status Desconhecido")
    print(f"Otimização concluída. Status: {status_text} ({problema.status})")

    sessoes_agendadas = []
    
    solucao_encontrada = problema.status == pulp.LpStatusOptimal or \
                        (problema.objective is not None and pulp.value(problema.objective) is not None)

    if solucao_encontrada:
        print("Uma solução viável foi encontrada. A extrair resultados...")
        for s in sessoes:
            if y[s].varValue is not None and y[s].varValue > 0.5:
                integrantes = [p for p in pessoas if x[p][s].varValue is not None and x[p][s].varValue > 0.5]
                sessao_info = df_sessoes[df_sessoes['Sessao'] == s].iloc[0]

                data_evento_dt = pd.to_datetime(sessao_info['Data do evento'])
                hora_inicio_dt = pd.to_datetime(str(sessao_info['Hora ini']))
                hora_fim_dt = pd.to_datetime(str(sessao_info['Hora fim']))

                sessoes_agendadas.append({
                    "nome_sessao": s,
                    "data_evento": data_evento_dt.strftime('%Y-%m-%d'),
                    "hora_inicio": hora_inicio_dt.strftime('%H:%M'),
                    "hora_fim": hora_fim_dt.strftime('%H:%M'),
                    "quantidade_pessoas": len(integrantes),
                    "integrantes": sorted(integrantes)
                })
        
        # --- VERIFICAÇÃO DE CONSISTÊNCIA ADICIONADA ---
        # Se o solver encontrou uma solução com valor, mas não conseguimos extrair nenhuma sessão,
        # é sinal de que a leitura dos resultados do PuLP falhou.
        objetivo_valor = pulp.value(problema.objective)
        if objetivo_valor is not None and objetivo_valor > 0 and not sessoes_agendadas:
            print("ERRO CRÍTICO: O solver encontrou uma solução, mas o PuLP não conseguiu ler os valores das variáveis.")
            raise ValueError("Falha na extração dos resultados da otimização. O PuLP pode ter uma incompatibilidade com o ambiente.")

    else:
        print("Otimização falhou ou não encontrou uma solução viável.")


    pessoas_nao_alocadas = [p for p in pessoas if nao_alocado[p].varValue is not None and nao_alocado[p].varValue > 0.5]
    print(f"Pessoas que não puderam ser alocadas: {pessoas_nao_alocadas}")

    resultado_final = {
        "total_sessoes_utilizadas": int(sum(y[s].varValue for s in sessoes if y[s].varValue is not None)),
        "sessoes_agendadas": sessoes_agendadas,
        "pessoas_nao_alocadas": sorted(pessoas_nao_alocadas)
    }

    return resultado_final

