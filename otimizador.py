import pandas as pd
import pulp

def otimizar_cronograma(df_sessoes, df_matriz, tempo_limite_segundos=120):
    """
    Função principal de otimização.
    Inclui restrições para evitar sessões sobrepostas.
    """
    
    # Extrai os nomes das sessoes e pessoas
    sessoes = df_matriz.index.tolist()
    pessoas = df_matriz.columns.tolist()

    # --- 1. CRIAÇÃO DO PROBLEMA ---
    problema = pulp.LpProblem("Alocacao_de_Pessoas", pulp.LpMinimize)

    # --- 2. DEFINIÇÃO DAS VARIÁVEIS DE DECISÃO ---
    x = pulp.LpVariable.dicts("Alocacao", (pessoas, sessoes), 0, 1, pulp.LpBinary)
    y = pulp.LpVariable.dicts("SessaoUtilizada", sessoes, 0, 1, pulp.LpBinary)
    nao_alocado = pulp.LpVariable.dicts("NaoAlocado", pessoas, 0, 1, pulp.LpBinary)

    # --- 3. DEFINIÇÃO DA FUNÇÃO OBJETIVO ---
    penalidade_nao_alocar = len(pessoas) + 1
    problema += pulp.lpSum(y[s] for s in sessoes) + \
                penalidade_nao_alocar * pulp.lpSum(nao_alocado[p] for p in pessoas)

    # --- 4. DEFINIÇÃO DAS RESTRIÇÕES ---
    
    # Restrições de Capacidade e Alocação Mínima
    for s in sessoes:
        capacidade = df_sessoes.loc[df_sessoes['Sessao'] == s, 'Capacidade'].iloc[0]
        problema += pulp.lpSum(x[p][s] for p in pessoas) <= capacidade * y[s]
        problema += pulp.lpSum(x[p][s] for p in pessoas) >= 1 * y[s]

    # Restrições de Disponibilidade
    for p in pessoas:
        for s in sessoes:
            if df_matriz.loc[s, p] == 0:
                problema += x[p][s] == 0

    # Restrição de Alocação Única por Pessoa (relaxada)
    for p in pessoas:
        problema += pulp.lpSum(x[p][s] for s in sessoes) + nao_alocado[p] == 1
        
    # --- NOVA RESTRIÇÃO: IMPEDIR SESSÕES SOBREPOSTAS ---
    # Mapeia o nome da sessão (string) para suas informações de tempo
    mapa_sessoes = df_sessoes.set_index('Sessao')
    
    print("Identificando sessões conflitantes...")
    conflitos_adicionados = 0
    # Itera sobre todos os pares únicos de sessões
    for i in range(len(sessoes)):
        for j in range(i + 1, len(sessoes)):
            s1_nome = sessoes[i]
            s2_nome = sessoes[j]

            s1 = mapa_sessoes.loc[s1_nome]
            s2 = mapa_sessoes.loc[s2_nome]

            # Pega os tempos de início e fim (já são datetime)
            s1_inicio = s1['Inicio_Sessao']
            s1_fim = s1['Fim_Sessao']
            s2_inicio = s2['Inicio_Sessao']
            s2_fim = s2['Fim_Sessao']

            # Lógica para verificar sobreposição (max(inicios) < min(fins))
            if max(s1_inicio, s2_inicio) < min(s1_fim, s2_fim):
                # Se as sessões s1 e s2 se sobrepõem, elas não podem
                # ser ativadas ao mesmo tempo.
                problema += y[s1_nome] + y[s2_nome] <= 1
                conflitos_adicionados += 1
                
    print(f"Restrições de conflito adicionadas: {conflitos_adicionados}")
    # --------------------------------------------------------------

    # --- 5. RESOLUÇÃO DO PROBLEMA COM LIMITE DE TEMPO ---
    print(f"Iniciando otimização com limite de tempo de {tempo_limite_segundos} segundos...")
    
    solver = pulp.PULP_CBC_CMD(timeLimit=tempo_limite_segundos)
    problema.solve(solver)
    
    status_resolucao = problema.status
    print(f"Otimização concluída. Status PuLP: {status_resolucao} ({pulp.LpStatus[status_resolucao]})")

    # --- 6. EXTRAÇÃO E FORMATAÇÃO DOS RESULTADOS ---
    
    objetivo_valor = pulp.value(problema.objective)
    solucao_encontrada = (status_resolucao == pulp.LpStatusOptimal) or \
                         (status_resolucao == pulp.LpStatusNotSolved and objetivo_valor is not None) or \
                         (objetivo_valor is not None) 

    if not solucao_encontrada:
        raise ValueError(f"Otimização falhou ou não encontrou solução. Status: {pulp.LpStatus[status_resolucao]}")

    sessoes_agendadas = []
    
    for s in sessoes:
        if y[s] is not None and y[s].varValue is not None and y[s].varValue > 0.5:
            integrantes = [p for p in pessoas if x[p][s] is not None and x[p][s].varValue is not None and x[p][s].varValue > 0.5]
            
            sessao_info = mapa_sessoes.loc[s]
            
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

    if objetivo_valor is not None and objetivo_valor > 0 and not sessoes_agendadas:
        print("ALERTA: Otimizador encontrou solução mas extração falhou.")
        raise ValueError("Falha na extração dos resultados da otimização. O solver encontrou uma solução, mas o PuLP não conseguiu lê-la. Tente novamente.")

    pessoas_nao_alocadas = []
    for p in pessoas:
        if nao_alocado[p] is not None and nao_alocado[p].varValue is not None and nao_alocado[p].varValue > 0.5:
            pessoas_nao_alocadas.append(p)

    print(f"Pessoas que não puderam ser alocadas: {pessoas_nao_alocadas}")

    resultado_final = {
        "total_sessoes_utilizadas": int(sum(y[s].varValue for s in sessoes if y[s].varValue is not None)),
        "sessoes_agendadas": sessoes_agendadas,
        "pessoas_nao_alocadas": sorted(pessoas_nao_alocadas)
    }

    return resultado_final