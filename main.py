import pandas as pd
from criar_sessoes import criar_sessoes
from criar_matriz import criar_matriz
from otimizador import otimizar_cronograma
import json

# --- INÍCIO DA EXECUÇÃO ORQUESTRADA ---
if __name__ == "__main__":
    # 1. PARÂMETROS DE ENTRADA (Isso virá da sua requisição HTTP no futuro)
    params_sessoes = {
        "data_inicio_str": '2025-08-11',
        "data_fim_str": '2025-12-19',
        "dias_da_semana": [0, 1, 2, 3, 4], # Seg a Sex
        "horarios_inicio_list": ['09:30','10:00','10:30', '14:30', '15:30'],
        "duracao_sessao_horas": 2,
        "capacidade_padrao": 45
    }
    
    # O usuário fornecerá o arquivo (via upload) e selecionará as equipes.
    caminho_arquivo_disponibilidade = 'otimizacao_react/dados/disponibilidade.xlsx' 
    equipes_para_processar = ["Operações"] # Este será o input do usuário.

    # --- ETAPA 1: Criar todas as sessões possíveis ---
    print("ETAPA 1: Gerando sessões...")
    df_sessoes = criar_sessoes(**params_sessoes)
    if not isinstance(df_sessoes, pd.DataFrame) or df_sessoes.empty:
        print(f"Erro ou nenhuma sessão criada.")
        exit()
    print(f"{len(df_sessoes)} sessões possíveis foram criadas.")

    # --- ETAPA 2: Criar a matriz de disponibilidade ---
    print("\nETAPA 2: Lendo disponibilidade e montando a matriz...")
    # A chamada agora é única e mais intuitiva, passando os parâmetros necessários.
    df_matriz = criar_matriz(df_sessoes, equipes_para_processar, caminho_arquivo_disponibilidade)
    
    if df_matriz.empty:
        print("Não foi possível criar a matriz de disponibilidade. Verifique os logs de erro.")
        exit()
    print("Matriz gerada com sucesso.")
    
    # --- ETAPA 3: Executar a otimização ---
    print("\nETAPA 3: Executando o otimizador...")
    resultado_otimizacao = otimizar_cronograma(df_sessoes, df_matriz)

    # --- ETAPA 4: Exibir o resultado final (em formato JSON) ---
    if resultado_otimizacao:
        print("\n--- RESULTADO DA OTIMIZAÇÃO ---")
        resultado_json = json.dumps(resultado_otimizacao, indent=4, ensure_ascii=False)
        print(resultado_json)
    else:
        print("A otimização falhou ou não encontrou uma solução.")