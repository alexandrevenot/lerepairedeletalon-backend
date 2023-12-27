import yaml
import smtplib
from email.message import EmailMessage

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/mailing/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def build_mail_content(
    logo_url: str,
    verification_link: str,
    title: str,
    header: str,
    action: str,
    button_name: str
    ) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>   
        <style>
            .container {{
                text-align: center;
                background-color: #F5F5F5; /* Couleur blanc cassé */
            }}
            .bouton-validation {{
                background-color: #007BFF;
                color: #fff;
                padding: 20px 40px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                margin-top: 20px;
                display: inline-block;
                text-align: center;
            }}
        </style>             
    </head>
    <body class="container">
        <header style="text-align: center;">
            <img src={logo_url} alt="Logo" width="150">
        </header>

        <div style="padding: 20px;">
            <h1>{header}</h1>
            <p>Cliquez sur le bouton ci-dessous pour {action}:</p>
            <p style="text-align: center;">
                <a href={verification_link} style="background-color: #3B7C35; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">{button_name}</a>
            </p>
        </div>

        <footer style="background-color: #f0f0f0; padding: 10px; text-align: center;">
            © 2023 Le Repaire de l'Étalon. Tous droits réservés.
        </footer>
    </body>
    </html>

    """

def send_email_verification_email(
    send_to: str,
    sent_from: str,
    logo_url: str,
    verification_link: str,
    sender_email: str,
    password: str,
    fromaddr: str,
    toaddrs: str
    ) -> None:
    message = EmailMessage()
    message["To"] = send_to
    message["From"] = sent_from
    message["Subject"] = 'Vérifiez votre adresse e-mail'
    message.set_content(build_mail_content(
        logo_url,
        verification_link,
        "Vérification de l'adresse e-mail",
        "Vérification de votre adresse e-mail",
        "vérifier votre adresse e-mail",
        "Vérifier mon adresse e-mail"
    ), subtype='html')

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo('Gmail')
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(fromaddr, toaddrs, message.as_string())

def send_password_update_email(
    send_to: str,
    sent_from: str,
    logo_url: str,
    verification_link: str,
    sender_email: str,
    password: str,
    fromaddr: str,
    toaddrs: str
    ) -> None:
    message = EmailMessage()
    message["To"] = send_to
    message["From"] = sent_from
    message["Subject"] = 'Changez votre mot de passe'
    message.set_content(build_mail_content(
        logo_url,
        verification_link,
        "Changement mot de passe",
        "Changement de votre mot de passe",
        "mettre à jour votre mot de passe",
        "Mettre à jour mon mot de passe"
    ), subtype='html')

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo('Gmail')
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(fromaddr, toaddrs, message.as_string())
