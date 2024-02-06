import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request
import requests
from datetime import datetime
import logging
import re

#SENHA DO GOOGLE: vuva vhkw mhft upbs

app = Flask(__name__, template_folder='templates')

# Configurar o logger
logging.basicConfig(level=logging.DEBUG)

def obter_taxa_juros_externa_para_mes_ano(tipo_contrato, ano, mes):
    try:
        # Escolha a URL da API com base no tipo de contrato
        if tipo_contrato == 'CreditoPessoalNaoConsignado':
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.25464/dados?formato=json&ano={ano}&mes={mes}'
        elif tipo_contrato == 'CreditoPessoalNaoConsignadoVinculado':
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.25465/dados?formato=json&ano={ano}&mes={mes}'
        elif tipo_contrato == 'CreditoPessoalConsignadoINSS':
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.25468/dados?formato=json&ano={ano}&mes={mes}'
        elif tipo_contrato == 'CreditoPessoalConsignadoTotal':
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.25469/dados?formato=json&ano={ano}&mes={mes}'
        elif tipo_contrato == 'AquisicaoVeiculos':
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.25471/dados?formato=json&ano={ano}&mes={mes}'
        else:
            raise ValueError('Tipo de contrato não reconhecido')

        # Realiza a requisição à API
        response = requests.get(url)

        # Verifica se a requisição foi bem-sucedida (código de resposta 200)
        if response.status_code == 200:
            dados = response.json()

            # Adiciona mensagens de depuração
            print(f"Dados da API para {ano}/{mes}: {dados}")

            # Verifica se há dados disponíveis
            if dados:
                # Convertendo a data de string para objeto datetime para facilitar a comparação
                data_desejada = datetime(int(ano), int(mes), 1)
                # Encontrar o registro mais próximo à data desejada
                registro_mais_proximo = min(dados, key=lambda x: abs(datetime.strptime(x['data'], '%d/%m/%Y') - data_desejada))

                taxa_juros_externa = float(registro_mais_proximo['valor'])
                return taxa_juros_externa
            else:
                raise ValueError("Não há dados disponíveis para o mês e ano informados.")
        else:
            raise ValueError(f"Erro na requisição à API. Código de resposta: {response.status_code}")

    except Exception as e:
        nome_mes = obter_nome_mes(int(mes))
        if nome_mes:
            print(f"Erro ao obter a taxa de juros externa para o mês de {nome_mes} e ano {ano}: {e}")
        else:
            print(f"Erro ao obter a taxa de juros externa para o mês {mes} e ano {ano}: {e}")
        return None

def obter_nome_mes(mes):
    # Mapeia o número do mês para o nome do mês
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    if 1 <= mes <= 12:
        return meses[mes - 1]
    else:
        return None

def converter_nome_mes_para_numero(nome_mes):
    # Converte o nome do mês para o valor numérico correspondente
    meses_dict = {
        "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
        "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
        "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
    }
    return meses_dict.get(nome_mes)

def validar_email(email):
    # Validação do e-mail usando regex (sugestão)
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def validar_celular(celular):
    # Validação do celular usando regex (sugestão)
    return bool(re.match(r'^\d{11}$', celular))

def calcular_financiamento(valor_prestacao, numero_prestacoes, taxa_mensal, tipo_contrato, ano_contrato, mes_contrato):
    try:
        numero_prestacoes = int(numero_prestacoes)
        valor_prestacao = float(valor_prestacao.replace(',', '.'))  # Substitui vírgula por ponto
        taxa_mensal_usuario = round(float(taxa_mensal.replace(',', '.')), 2)  # Arredonda a taxa para duas casas decimais

        # Atualização: Obter a taxa de juros externa para o mês e ano do contrato
        taxa_juros_externa = obter_taxa_juros_externa_para_mes_ano(tipo_contrato, ano_contrato, mes_contrato)

        # Verificar se a taxa de juros externa foi obtida corretamente
        if taxa_juros_externa is None or not taxa_juros_externa:
            raise ValueError(f"Não foi possível obter a taxa de juros externa para o mês {mes_contrato} e ano {ano_contrato}.")

        # Imprimir detalhes para ajudar a entender o problema
        print(f"Taxa de juros informada: {taxa_mensal_usuario}")
        print(f"Taxa de juros externa para {obter_nome_mes(int(mes_contrato))}/{ano_contrato}: {taxa_juros_externa}")

        if abs(taxa_mensal_usuario < taxa_juros_externa):
            raise ValueError(f"A taxa de juros informada ({taxa_mensal_usuario}) não corresponde à taxa de juros externa ({taxa_juros_externa}) para o mês {obter_nome_mes(int(mes_contrato))} de {ano_contrato}.")

        valor_financiado = valor_prestacao / ((taxa_mensal_usuario / 100 * ((1 + taxa_mensal_usuario / 100) ** numero_prestacoes)) / (((1 + taxa_mensal_usuario / 100) ** numero_prestacoes) - 1))
        total_financiado = valor_prestacao * numero_prestacoes
        juros = total_financiado - valor_financiado

        return valor_financiado, total_financiado, juros, None

    except ValueError as ve:
        return None, None, None, str(ve)

# Atualize a função enviar_email para aceitar dados_cliente
def enviar_email(nome, email, valor_financiado, total_financiado, juros, dados_cliente):
    try:
        assunto = 'Resultado do Financiamento'
        corpo = f"Olá {nome},\n\nO financiamento foi calculado com sucesso!\n\nDetalhes do Financiamento:\n\n" \
        f"Informações do Cliente:\n" \
        f"Nome: {dados_cliente['nome']}\n" \
        f"Número de Celular: {dados_cliente['celular']}\n" \
        f"E-mail: {dados_cliente['email']}\n" \
        f"Valor da Prestação: {dados_cliente['valor_prestacao']}\n" \
        f"Número de Prestações: {dados_cliente['numero_prestacoes']}\n" \
        f"Taxa de Juros Mensal (%): {dados_cliente['taxa_mensal']}\n" \
        f"Ano e Mês do Contrato: {dados_cliente['ano_contrato']}/{dados_cliente['mes_contrato']}\n\n" \
        f"Valor Financiado: R$ {round(valor_financiado, 2)}\n" \
        f"Total Financiado: R$ {round(total_financiado, 2)}\n" \
        f"Juros: R$ {round(juros, 2)}\n"

        # Configurações do servidor SMTP do Gmail
        servidor_smtp = smtplib.SMTP('smtp.gmail.com', 587)
        servidor_smtp.starttls()
        servidor_smtp.login('perusovanz@gmail.com', 'vuvavhkwmhftupbs')

        # Construir o e-mail
        mensagem = MIMEMultipart()
        mensagem['From'] = 'perusovanz@gmail.com'
        mensagem['To'] = 'PERUSOVANZ@GMAIL.COM'  # Alterado para o destinatário desejado
        mensagem['Subject'] = assunto
        mensagem.attach(MIMEText(corpo, 'plain'))

        # Enviar o e-mail
        servidor_smtp.sendmail('perusovanz@gmail.com', 'PERUSOVANZ@GMAIL.COM', mensagem.as_string())

        # Finaliza a conexão com o servidor SMTP
        servidor_smtp.quit()

        print(f"E-mail enviado para PERUSOVANZ@GMAIL.COM com sucesso!")

    except Exception as e:
        print(f"Erro ao enviar e-mail para PERUSOVANZ@GMAIL.COM: {e}")

@app.route('/')
def index():
    current_year = datetime.now().year
    return render_template('index.html', current_year=current_year, nome_mes=obter_nome_mes)

@app.route('/calcular_financiamento', methods=['POST'])
def calcular_financiamento_rota():
    valor_prestacao = request.form.get('valor_prestacao')
    numero_prestacoes = request.form.get('numero_prestacoes')
    taxa_mensal = request.form.get('taxa_mensal')
    tipo_contrato = request.form.get('tipo_contrato')
    ano_contrato = request.form.get('ano_contrato')
    mes_contrato = request.form.get('mes_contrato')
    nome = request.form.get('nome')
    celular = request.form.get('celular')
    email = request.form.get('email')

    # Validação do e-mail
    email_valido = validar_email(email) if email else True

    # Validação do celular
    celular_valido = validar_celular(celular) if celular else True

    valor_financiado, total_financiado, juros, error_message = None, None, None, None

    if not (nome and celular_valido and email_valido):
        # Retorne uma mensagem de erro, por exemplo.
        return 'Por favor, preencha todos os campos obrigatórios corretamente.'

    # Atribua valores às variáveis dentro do bloco if
    valor_financiado, total_financiado, juros, error_message = calcular_financiamento(
        valor_prestacao, numero_prestacoes, taxa_mensal, tipo_contrato, ano_contrato, mes_contrato
    )

    if valor_financiado is not None:
        success = True

        # Criar um dicionário com as informações do cliente
        dados_cliente = {
            'nome': nome,
            'celular': celular,
            'email': email,
            'valor_prestacao': valor_prestacao,
            'numero_prestacoes': numero_prestacoes,
            'taxa_mensal': taxa_mensal,
            'ano_contrato': ano_contrato,
            'mes_contrato': mes_contrato
        }

        # Enviar e-mail com informações do cliente
        enviar_email(nome, email, valor_financiado, total_financiado, juros, dados_cliente)

        return render_template(
            'resultado.html',
            valor_financiado=round(valor_financiado, 2),
            total_financiado=round(total_financiado, 2),
            juros=round(juros, 2),
            success=success
        )
    else:
        success = False
        return render_template(
            'resultado.html',
            error_message=error_message,
            success=success
        )
      

if __name__ == '__main__':
    app.run(debug=True)


