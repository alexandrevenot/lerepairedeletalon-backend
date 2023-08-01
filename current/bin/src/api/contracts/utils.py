import yaml
import aiohttp

import src.api.pricing.utils as pricing_utils

pricing_config = pricing_utils.load_config()

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/contracts/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def build_company_identification_field(
    company_name: str,
    company_status: str,
    capital: str,
    head_office_address: str,
    siret: str,
    representative_gender: str,
    representative_firstname: str,
    representative_lastname: str
):
    res = f"La société {company_name}, {company_status} au capital de {capital}, donc le siège social est au {head_office_address}, "
    res += f"immatriculée au registre du commerce et des sociétés de la chambre de commerce et d'industrie de Paris, sous le numéro de SIRET {siret}, "
    res += f"représentée par {'Monsieur' if gender == 'male' else 'Madame'} {firstname} {lastname.upper()}"
    return res

def build_person_identification_field(
    gender: str,
    firstname: str,
    lastname: str,
    postal_address: str,
    birthdate: str,
    birthplace: str,
    citizenship: str
):
    res = f"{'Monsieur' if gender == 'male' else 'Madame'} {firstname} {lastname.upper()}, "
    res += f"Demeurant au {postal_address}, "
    res += f"Né{'' if gender == 'male' else 'e'} le {birthdate}, "
    res += f"À {birthplace}, "
    res += f"De nationalité {citizenship}"
    return res

def build_last_payment_cases():
    res = "La jument, à l'issue de la saillie dont ce contrat fait l'objet, obtient un poulain, et ce poulain a passé le seuil des 48h en vie. "
    res += "Dans ce cas, la seconde fraction devra être payée dans le délai d'un mois après les 48h du poulain.\n"
    res += "La jument a été vendue entre le payment de la première fraction et celui de la seconde. Dans ce cas, la seconde fraction doit être payée dans le délai d'un mois suivant l'acte de vente.\n"
    return res

def build_use_conditions(insemination_center: str):
    res = f"La jument sera inséminée dans le centre d'insémination agréé {insemination_center}"
    res += "Le prix de la saillie inclut le prix de fabrication des doses, ainsi que leur acheminement dans le centre d'insémination.\n"
    res += "Les doses seront envoyées au centre d'insémination sur demande.\n"
    res += "L'acheteur atteste avoir connaissance des conditions dans lesquelles se déroulent les inséminations, ainsi que les risques associés.\n"
    res += "Tous les frais générés par la saillie autres que la fabrication des doses et leur acheminement sont à la charge de l'Acheteur.\n"
    return res

async def create_and_send_contract(
    template_id: str,
    cover_document: dict,
    buyer_document: dict,
    seller_document: dict,
    test: bool,
    expires_in_hours: int,
    signature_request_delivery_method: str,
    signed_document_delivery_method: str,
    required_identification_methods: list[str],
    token: str
):

    signers = []

    buyer_signer_dict = {}
    buyer_signer_dict["name"] = f"{buyer_document['firstname']} {buyer_document['firstname'].upper()}"
    buyer_signer_dict["email"] = buyer_document["email"]
    buyer_signer_dict["mobile"] = buyer_document["phone_number"]
    if "company_name" in buyer_document:
        buyer_signer_dict["company_name"] = buyer_document["company_name"]
    buyer_signer_dict["signing_order"] = "1"
    buyer_signer_dict["signature_request_delivery_method"] = signature_request_delivery_method
    buyer_signer_dict["signed_document_delivery_method"] = signed_document_delivery_method
    buyer_signer_dict["required_identification_methods"] = required_identification_methods
    #buyer_signer_dict["redirect_url"] = redirect_url
    signers.append(buyer_signer_dict)

    seller_signer_dict = {}
    seller_signer_dict["name"] = f"{seller_document['firstname']} {seller_document['firstname'].upper()}"
    seller_signer_dict["email"] = seller_document["email"]
    seller_signer_dict["mobile"] = seller_document["phone_number"]
    if "company_name" in seller_document:
        seller_signer_dict["company_name"] = seller_document["company_name"]
    seller_signer_dict["signing_order"] = "2"
    seller_signer_dict["signature_request_delivery_method"] = signature_request_delivery_method
    seller_signer_dict["signed_document_delivery_method"] = signed_document_delivery_method
    seller_signer_dict["required_identification_methods"] = required_identification_methods
    #seller_signer_dict["redirect_url"] = redirect_url
    signers.append(seller_signer_dict)

    placeholder_fields = []
    placeholder_fields.append({
        "api_key": "seller_identification",
        "value": build_company_identification_field(
            seller_document["company_name"],
            seller_document["company_status"],
            seller_document["capital"],
            seller_document["head_office_address"],
            seller_document["siret"],
            seller_document["representative_gender"],
            seller_document["representative_firstname"],
            seller_document["representative_lastname"]
        )
    })
    
    if buyer_document["status"] == "company":
        placeholder_fields.append({
            "api_key": "buyer_identification",
            "value": build_person_identification_field(
                buyer_document["gender"],
                buyer_document["firstname"],
                buyer_document["lastname"],
                buyer_document["postal_address"],
                buyer_document["birthdate"],
                buyer_document["birthplace"],
                buyer_document["citizenship"]
            )
        })
    elif buyer_document["status"] == "individual":
        placeholder_fields.append({
            "api_key": "buyer_identification",
            "value": build_company_identification_field(
                buyer_document["company_name"],
                buyer_document["company_status"],
                buyer_document["capital"],
                buyer_document["head_office_address"],
                buyer_document["siret"],
                buyer_document["representative_gender"],
                buyer_document["representative_firstname"],
                buyer_document["representative_lastname"]
            )
        })
    
    for field in ["stallion_name", "stallion_breed", "mare_name", "mare_breed"]:
        placeholder_fields.append({
            "api_key": field,
            "value": cover_document[field]
        })
    
    half_payment_value = pricing_utils.calculate_checkout(
        cover_document["subtotal"],
        cover_document["buyer_fees"],
        pricing_config["TVA_coeff_HT"]
    ).subtotal / 2

    for field in ["down_payment", "last_payment"]:
        placeholder_fields.append({
            "api_key": field,
            "value": half_payment_value
        })
    
    placeholder_fields.append({
        "api_key": "last_payment_validity_cases",
        "value": build_last_payment_cases()
    })

    placeholder_fields.append({
        "api_key": "use_conditions",
        "value": build_use_conditions(cover_document["insemination_center"])
    })

    data = {
        "template_id": template_id,
        "test": test,
        "title": "Contrat de saillie",
        "locale": "fr",
        "expires_in_hours": expires_in_hours,
        #"custom_webhook_url": "https://lerepairedeletalon.fr/esignaturesio-custom-webhook",
        "labels": [cover_document["cover_type"].upper()],
        "signers": signers,
        "placeholder_fields": placeholder_fields,
        "emails": {
            "signature_request_subject": "Votre contrat de saillie est prêt pour signature",
            "signature_request_text": "Bonjour __FULL_NAME__,\n\nPour vérifier et signer votre contrat de saillie, cliquez sur le bouton ci-dessous.",
            "final_contract_subject": "La signature de votre document est terminée",
            "final_contract_text": "Bonjour __FULL_NAME__,\n\nLa signature de votre document est terminée.\n\nMerci pour votre confiance."
        }
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://esignatures.io/api/contracts?token={token}"
        async with session.post(url, json=data) as response:
            json = await response.json()
            assert response.status == 200, f"POST on https://esignatures.io/api/contracts?token={token} : received status {response.status} with json {json}"

            return json