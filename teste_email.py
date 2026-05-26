import json, smtplib
with open('credenciais.json') as f:
    c = json.load(f)
with smtplib.SMTP('smtp.gmail.com', 587) as s:
    s.ehlo()
    s.starttls()
    s.login(c['email_remetente'], c['senha_app'])
    print('Autenticacao OK!')
