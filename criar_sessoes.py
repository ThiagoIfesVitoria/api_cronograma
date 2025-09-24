# criar_sessoes_logic.py
from datetime import datetime, timedelta
import locale
import pandas as pd

def criar_sessoes(data_inicio_str, data_fim_str, dias_da_semana, horarios_inicio_list, duracao_sessao_horas, capacidade_padrao):
    """
    Gera todas as sessões possíveis com base nos parâmetros fornecidos.
    Retorna um DataFrame do pandas com as sessões ou uma string de erro.
    """
    try:
        # Tenta definir a localidade para PT-BR. UTF-8 para sistemas Unix/macOS
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        try:
            # Tenta definir a localidade para PT-BR para Windows
            locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
        except locale.Error:
            print("Aviso: Não foi possível definir a localidade para português. Nomes de meses serão em inglês.")
            pass # Continua sem a localidade PT-BR se falhar

    try:
        data_inicio_dt = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        data_fim_dt = datetime.strptime(data_fim_str, '%Y-%m-%d')
    except ValueError:
        return "Erro: Formato de data inválido. Use YYYY-MM-DD."

    if data_inicio_dt > data_fim_dt:
        return "Erro: Data de início não pode ser posterior à data de fim."

    sessoes_geradas = []
    contador_s = 1 # Contador para o nome da sessão

    delta = data_fim_dt - data_inicio_dt

    for i in range(delta.days + 1):
        data_evento = data_inicio_dt + timedelta(days=i)

        if data_evento.weekday() in dias_da_semana:
            for horario_ini_str in horarios_inicio_list:
                try:
                    horario_inicio_dt = datetime.strptime(horario_ini_str, '%H:%M').time()
                except ValueError:
                    return f"Erro: Formato de horário inválido '{horario_ini_str}'. Use HH:MM."

                data_e_hora_inicio = datetime.combine(data_evento.date(), horario_inicio_dt)
                data_e_hora_fim = data_e_hora_inicio + timedelta(hours=duracao_sessao_horas)
                mes_evento = data_evento.strftime('%B')
                
                sessoes_geradas.append({
                    'Sessao': f'sessao {contador_s}', # Adição da coluna 'Sessao'
                    'Data do evento': data_evento.strftime('%Y-%m-%d'),
                    'Hora ini': horario_ini_str,
                    'Hora fim': data_e_hora_fim.strftime('%H:%M'),
                    'Capacidade': capacidade_padrao,
                    'Mês do evento': mes_evento
                })
                contador_s += 1 # Incrementa o contador
    
    if not sessoes_geradas:
        return "Nenhuma sessão gerada com os parâmetros fornecidos. Verifique as datas e dias da semana."

    df_sessoes = pd.DataFrame(sessoes_geradas)
    return df_sessoes 