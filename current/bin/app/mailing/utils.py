import yaml
import smtplib
from email.message import EmailMessage

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/mailing/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()
global_config = load_global_config()

def build_email_content(
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
                background-color: #f7faf7;
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
            <img src={config["logo_url"]} alt="Logo" width="150">
        </header>

        <div style="padding: 20px;">
            <h1>{header}</h1>
            <p>Cliquez sur le bouton ci-dessous pour {action}:</p>
            <p style="text-align: center;">
                <a href={verification_link} style="background-color: #3B7C35; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">{button_name}</a>
            </p>
        </div>

        <footer style="background-color: #f0f0f0; padding: 10px; text-align: center;">
            © 2024 SAS LRDE. Tous droits réservés.
        </footer>
    </body>
    </html>

    """

def send_action_email(
    email_type: str,
    send_to: str,
    code: str,
    toaddrs: str
) -> None:
    message = EmailMessage()
    message["To"] = send_to
    message["From"] = global_config["company_name"]

    if email_type == "email_verification":
        message["Subject"] = 'Vérifiez votre adresse e-mail'
        message.set_content(build_email_content(
            f"{global_config['frontend_url']}{config['email_verification_route']}?code={code}",
            "Vérification de l'adresse e-mail",
            "Vérification de votre adresse e-mail",
            "vérifier votre adresse e-mail",
            "Vérifier mon adresse e-mail"
        ), subtype='html')
    elif email_type == "password_update":
        message["Subject"] = 'Changez votre mot de passe'
        message.set_content(build_email_content(
            f"{global_config['frontend_url']}{config['password_update_page']}?code={code}",
            "Changement de mot de passe",
            "Changement de votre mot de passe",
            "mettre à jour votre mot de passe",
            "Mettre à jour mon mot de passe"
        ), subtype='html')

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo('Gmail')
        server.starttls()
        server.login(config["service_email"], config["password"])
        server.sendmail(config["service_email"], toaddrs, message.as_string())

def send_notification_email(
    send_to: str,
    toaddrs: str,
    contact_firstname: str,
    new_status: str,
    destination_pov: str
):
    if destination_pov == "buyer" and new_status == "requested":
        return

    message = EmailMessage()
    message["To"] = send_to
    message["From"] = global_config["company_name"]
    if destination_pov == "seller":
        if new_status == "requested":
            message["Subject"] = 'Nouvelle demande de saillie'
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Nouvelle demande de saillie",
                f"Nouvelle demande de saillie de {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')
        elif new_status == "buyersigned":
            message["Subject"] = "Contrat signé par l'acheteur"
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Contrat signé par l'acheteur",
                f"Contrat signé par {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')
        elif new_status == "downpaid":
            message["Subject"] = "Acompte payé par l'acheteur"
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Acompte payé par l'acheteur",
                f"Acompte payé par {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')
        elif new_status == "fullypaid":
            message["Subject"] = "Solde payé par l'acheteur"
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Solde payé par l'acheteur",
                f"Solde payé par {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')
    elif destination_pov == "buyer":
        if new_status == "denied":
            message["Subject"] = "Saillie refusée par le vendeur"
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Saillie refusée par le vendeur",
                f"Saillie refusée par {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')
        elif new_status == "approved":
            message["Subject"] = "Saillie acceptée par le vendeur"
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Saillie acceptée par le vendeur",
                f"Saillie acceptée par {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')
        elif new_status == "sellersigned":
            message["Subject"] = "Contrat signé par le vendeur"
            message.set_content(build_email_content(
                f"{global_config['frontend_url']}/dashboard",
                "Contrat signé par le vendeur",
                f"Contrat signé par {contact_firstname}",
                "consulter votre tableau de bord",
                "Consulter mon tableau de bord"
            ), subtype='html')

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo('Gmail')
        server.starttls()
        server.login(config["service_email"], config["password"])
        server.sendmail(config["service_email"], toaddrs, message.as_string())
