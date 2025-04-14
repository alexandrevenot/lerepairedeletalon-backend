import yaml
import aiohttp
from datetime import timedelta

import routers.payments.utils as payments_utils
import routers.stallions.utils as stallions_utils

payments_config = payments_utils.load_config()
stallions_config = stallions_utils.load_config()

def load_global_config() -> dict:
    with open('etc/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('etc/contracts/config.yaml', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()

def build_identification_field(stallion_owner_in_db: None | dict, user_in_db: dict):
    if stallion_owner_in_db is None:
        mapping = user_in_db["legal_identity"]
    else:
        mapping = stallion_owner_in_db

    if mapping["business_type"] == "individual":
        field = f'{mapping["gender"]} '
        if stallion_owner_in_db is None:
            field += f'{user_in_db["firstname"]} {user_in_db["lastname"]}, '
        else:
            field += f'{mapping["firstname"]} {mapping["lastname"]}, '
        field += f'né{"" if mapping["gender"] == "Monsieur" else "e"} le {mapping["birthdate"]} '
        field += f'à {mapping["birthplace"]}, '
        field += f'de nationalité {mapping["citizenship"]}, '
        field += f'demeurant {mapping["address_line1"]}, '
        if "address_line2" in mapping and mapping["address_line2"] != "":
            field += f'{mapping["address_line2"]}, '
        field += f'{mapping["address_postal_code"]} {mapping["address_city"]}, '
        field += "ou toute autre personne mandatée à l'effet des présentes."
    else:
        field = f'La société {mapping["company_name"]}, {mapping["company_structure"]} '
        field += f'au capital de {mapping["capital"]} euros, immatriculée '
        if "rcs" in mapping and mapping["rcs"] != "":
            field += f'au Registre du Commerce et des Sociétés de {mapping["rcs"]} '
        field += f'sous le numéro {mapping["siren"]}, dont le siège social est situé '
        field += f'{mapping["head_office_address_line1"]}, '
        if "head_office_address_line2" in mapping and mapping["head_office_address_line2"] != "":
            field += f'{mapping["head_office_address_line2"]}, '
        field += f'{mapping["head_office_address_postal_code"]} '
        field += f'{mapping["head_office_address_city"]}, représentée par '
        field += f'{user_in_db["firstname"]} {user_in_db["lastname"]}, en qualité de '
        field += f"{user_in_db['legal_identity']['role_in_company']}, ayant tous pouvoirs à l'effet des présentes, "
        field += "ou toute autre personne mandatée à l'effet des présentes."

    return field

def build_pedigree_field(pedigree: str):
    parents = [
        "Père",
        "Mère",
        "Père du père",
        "Mère du père",
        "Père du père du père",
        "Mère du père du père",
        "Père de la mère du père",
        "Mère de la mère du père",
        "Père de la mère",
        "Mère de la mère",
        "Père du père de la mère",
        "Mère du père de la mère",
        "Père de la mère de la mère",
        "Mère de la mère de la mère"
    ]

    return ", ".join([f'{parent}: {name}' for parent, name in zip(parents, pedigree) if name != ""])

def build_balance_payment_conditions(balance_payment_condition):
    field = ""
    if balance_payment_condition == "covered":
        field += "L'Évènement sera considéré comme s'étant produit et la condition sera considérée comme étant réalisée "
        field += "au jour de la réception par le Vendeur d'un certificat vétérinaire de gravidité attestant de l'état de "
        field += "gestation de la Jument à la suite de la Saillie par l'Étalon.\n"
        field += "L'Évènement sera considéré comme ne s'étant pas produit au jour de la réception par le Vendeur d'un "
        field += "certificat vétérinaire attestant de la vacuité de la Jument.\n"
        field += "L'Acheteur s'engage à adresser une copie du certificat vétérinaire de gravidité ou de vacuité au Vendeur "
        field += "dans un délai compris entre 27 et 32 jours à compter du jour de la Saillie, par lettre recommandée "
        field += "avec accusé de réception.\n"
        field += "À défaut de production d'un certificat vétérinaire de gravidité ou de vacuité par l'Acheteur dans le délai "
        field += "susmentionné, attestant de l'état de la Jument, la Jument sera réputée gestante et l'Évènement sera "
        field += "considéré comme s'étant réalisé à la date d'expiration du délai susmentionné."
    elif balance_payment_condition == "covered_1_10":
        field += "L'Évènement sera considéré comme ne s'étant pas produit si au 15 octobre de l'année en cours l'Acheteur "
        field += "n'a pas adressé par lettre recommandée avec accusé de réception au Vendeur un certificat vétérinaire "
        field += "attestant de la vacuité de la Jument au 1er octobre de l'année en cours.\n"
        field += "À défaut de production d'un certificat vétérinaire de vacuité par l'Acheteur dans le délai susmentionné, "
        field += "attestant de l'état de la Jument, la Jument sera réputée gestantée au 1er octobre de l'année en cours "
        field += "et l'Évènement sera considéré comme s'étant réalisé à cette date."
    elif balance_payment_condition == "living_foal":
        field += "L'Évènement sera considéré comme ne s'étant pas produit au jour de la réception par le Vendeur d'un "
        field += "certificat vétérinaire, adressé par lettre recommandée avec accusé de réception par l'Acheteur dans un "
        field += "délai de 15 jours à compter de la date de mise bas par la Jument, attestant que la gestation de la Jument "
        field += "suite à la Saillie par l'Étalon est terminée et qu'aucun Poulain Vivant, au sens de l'article 1 du présent "
        field += "contrat, n'est né de cette même Saillie.\n"
        field += "Aucun certificat vétérinaire établi avant la date de mise bas par la Jument, et attestant de manière anticipée "
        field += "qu'aucun Poulain Vivant ne pourra naître de la Saillie, ne permet de considérer l'Évènement comme non-réalisé "
        field += "au sens du présent article.\n"
        field += "En cas de gestation multiple, les Parties conviennent que l'Évènement est considéré comme réalisé à la date d'un "
        field += "an après la Saillie, dès lors que l'Acheteur a mené la gestation à terme sans ne laisser qu'une vésicule en "
        field += "procédant à l'élimination des autres et qu'aucun Poulain Vivant n'est né, à moins pour l'Acheteur de prouver, par "
        field += "un certificat vétérinaire établi entre le 27ème et le 32ème jour après la Saillie, "
        field += "qu'il n'avait pas connaissance du caractère multiple de la gestation.\n"
        field += "À défaut de production d'un certificat vétérinaire par l'Acheteur dans le délai d'un an après la date de la Saillie, "
        field += "attestant du terme de la gestation de la Jument suite à la Saillie par l'Étalon et du défaut de naissance de tout Poulain "
        field += "Vivant de cette même Saillie, l'Évènement sera considéré comme s'étant réalisé à la date d'un an après la Saillie."
    elif balance_payment_condition == "living_foal_48":
        field += "L'Évènement sera considéré comme ne s'étant pas produit au jour de la réception par le Vendeur d'un "
        field += "certificat vétérinaire, adressé par lettre recommandée avec accusé de réception par l'Acheteur dans un "
        field += "délai de 15 jours à compter de la date de mise bas par la Jument, attestant que la gestation de la Jument "
        field += "suite à la Saillie par l'Étalon est terminée et qu'aucun Poulain Vivant, au sens de l'article 1 du présent "
        field += "contrat, n'est né de cette même Saillie et a atteint les 48 heures en vie.\n"
        field += "Aucun certificat vétérinaire établi avant la date de mise bas par la Jument, et attestant de manière anticipée "
        field += "qu'aucun Poulain Vivant et atteignant les 48 heures en vie ne pourra naître de la Saillie, ne permet de "
        field += "considérer l'Évènement comme non-réalisé au sens du présent article.\n"
        field += "En cas de gestation multiple, les Parties conviennent que l'Évènement est considéré comme réalisé à la date d'un "
        field += "an après la Saillie, dès lors que l'Acheteur a mené la gestation à terme sans ne laisser qu'une vésicule en "
        field += "procédant à l'élimination des autres et qu'aucun Poulain Vivant n'est né et a atteint les 48 heures en vie, à moins "
        field += "pour l'Acheteur de prouver, par un certificat vétérinaire établi entre le 27ème et le 32ème jour après la Saillie, "
        field += "qu'il n'avait pas connaissance du caractère multiple de la gestation.\n"
        field += "À défaut de production d'un certificat vétérinaire par l'Acheteur dans le délai d'un an après la date de la Saillie, "
        field += "attestant du terme de la gestation de la Jument suite à la Saillie par l'Étalon et du défaut de naissance et "
        field += "de l'atteinte des 48 heures en vie de tout Poulain Vivant de cette même Saillie, l'Évènement sera considéré comme "
        field += "s'étant réalisé à la date d'un an après la Saillie."

    return field

async def create_and_send_contract(
    template_id: str,
    cover_document: dict,
    buyer_document: dict,
    seller_document: dict,
    stallion_owner_document: dict | None,
    test: bool,
    expires_in_hours: int,
    signature_request_delivery_methods: list[str],
    signed_document_delivery_method: str,
    multi_factor_authentications: list[str],
    frontend_url: str,
    esignatures_contracts_api_url: str,
    token: str
):

    signers = []

    buyer_signer_dict = {}
    buyer_signer_dict["name"] = f"{buyer_document['firstname']} {buyer_document['lastname'].upper()}"
    buyer_signer_dict["email"] = buyer_document["email"]
    buyer_signer_dict["mobile"] = '+33' + buyer_document["phone_number"][1:]
    if buyer_document["legal_identity"]["business_type"] == "company":
        buyer_signer_dict["company_name"] = buyer_document["legal_identity"]["company_name"]
    buyer_signer_dict["signing_order"] = "1"
    buyer_signer_dict["signature_request_delivery_methods"] = signature_request_delivery_methods
    buyer_signer_dict["signed_document_delivery_method"] = signed_document_delivery_method
    buyer_signer_dict["multi_factor_authentications"] = multi_factor_authentications
    buyer_signer_dict["redirect_url"] = f"{frontend_url}/tableau-de-bord?coverId={str(cover_document['_id'])}&pollCoverStatus=buyersigned"
    signers.append(buyer_signer_dict)

    seller_signer_dict = {}
    seller_signer_dict["name"] = f"{seller_document['firstname']} {seller_document['lastname'].upper()}"
    seller_signer_dict["email"] = seller_document["email"]
    seller_signer_dict["mobile"] = '+33' + seller_document["phone_number"][1:]
    if seller_document["legal_identity"]["business_type"] == "company":
        seller_signer_dict["company_name"] = seller_document["legal_identity"]["company_name"]
    seller_signer_dict["signing_order"] = "2"
    seller_signer_dict["signature_request_delivery_methods"] = signature_request_delivery_methods
    seller_signer_dict["signed_document_delivery_method"] = signed_document_delivery_method
    seller_signer_dict["multi_factor_authentications"] = multi_factor_authentications
    seller_signer_dict["redirect_url"] = f"{frontend_url}/tableau-de-bord?coverId={str(cover_document['_id'])}&pollCoverStatus=sellersigned"
    signers.append(seller_signer_dict)

    placeholder_fields = []
    placeholder_fields.append({
        "api_key": "stallion_owner_identification",
        "value": build_identification_field(stallion_owner_document, seller_document)
    })

    placeholder_fields.append({
        "api_key": "buyer_identification",
        "value": build_identification_field(None, buyer_document)
    })

    for field in ["stallion_name", "stallion_nsire", "stallion_breed", "stallion_color", \
                  "mare_name", "mare_breed", "mare_nsire", "mare_pregnancy_history", \
                    "stallion_offspring", "stallion_performance", "stallion_pedigree_po"]:
        placeholder_fields.append({
            "api_key": field,
            "value": cover_document[field]
        })

    placeholder_fields.append({
        "api_key": "stallion_height",
        "value": str(cover_document["stallion_height"]) + ' centimètres'
    })

    placeholder_fields.append({
        "api_key": "stallion_birthdate",
        "value": cover_document["stallion_birthdate"].strftime('%d/%m/%Y')
    })

    placeholder_fields.append({
        "api_key": "stallion_production_breeds",
        "value": ', '.join(cover_document["stallion_production_breeds"])
    })

    placeholder_fields.append({
        "api_key": "stallion_pedigree",
        "value": build_pedigree_field(cover_document["stallion_pedigree"])
    })

    placeholder_fields.append({
        "api_key": "cover_place",
        "value": cover_document["cover_specs"]["cover_place"]
    })

    placeholder_fields.append({
        "api_key": "cover_type",
        "value": config["cover_technique_names"][cover_document["cover_type"]]
    })

    placeholder_fields.append({
        "api_key": "arrival_date",
        "value": cover_document["arrival_date"].strftime('%d/%m/%Y')
    })

    placeholder_fields.append({
        "api_key": "maximum_nb_of_attempts",
        "value": cover_document["cover_specs"]["maximum_nb_of_attempts"]
    })

    placeholder_fields.append({
        "api_key": "total_ttc",
        "value": cover_document["total"]
    })

    placeholder_fields.append({
        "api_key": "advance_percentage",
        "value": cover_document["cover_specs"]["advance_percentage"]
    })

    advance_subtotal = payments_utils.calculate_advance(cover_document["subtotal"], cover_document["cover_specs"]["advance_percentage"])
    advance_fees = payments_utils.calculate_advance(cover_document["fees"], cover_document["cover_specs"]["advance_percentage"])

    placeholder_fields.append({
        "api_key": "advance_ttc",
        "value": advance_subtotal + advance_fees
    })

    placeholder_fields.append({
        "api_key": "balance_payment_condition_content",
        "value": build_balance_payment_conditions(cover_document["cover_specs"]["balance_payment_condition"])
    })

    if stallion_owner_document is None:
        placeholder_fields.append({
            "api_key": "stallion_owner_gender_and_name",
            "value": f'{seller_document["legal_identity"]["gender"]} {seller_document["firstname"]} {seller_document["lastname"].upper()}'
        })
    else:
        placeholder_fields.append({
            "api_key": "stallion_owner_gender_and_name",
            "value": f'{stallion_owner_document["gender"]} {stallion_owner_document["firstname"]} {stallion_owner_document["lastname"].upper()}'
        })

    placeholder_fields.append({
        "api_key": "buyer_gender_and_name",
        "value": f'{buyer_document["legal_identity"]["gender"]} {buyer_document["firstname"]} {buyer_document["lastname"].upper()}'
    })

    for disease in ["metrite", "arterite", "anemie"]:
        # for the stallion
        try:
            first_field_to_append = {
                "api_key": f"stallion_{disease}_test_date",
                "value": cover_document["stallion_std_negative_tests"][disease]["test_date"]
            }
            second_field_to_append = {
                "api_key": f"stallion_{disease}",
                "value": "Oui"
            }
            placeholder_fields.append(first_field_to_append)
            placeholder_fields.append(second_field_to_append)
        except KeyError:
            first_field_to_append = {
                "api_key": f"stallion_{disease}_test_date",
                "value": "néant"
            }
            second_field_to_append = {
                "api_key": f"stallion_{disease}",
                "value": "Non"
            }
            placeholder_fields.append(first_field_to_append)
            placeholder_fields.append(second_field_to_append)

        # for the mare
        try:
            test_oldness = cover_document["cover_specs"]["demanded_std_negative_tests"][disease]["test_oldness"]
            first_field_to_append = {
                "api_key": f"mare_{disease}_test_date",
                "value": f"Entre le {(cover_document['arrival_date'] - timedelta(days=test_oldness)).strftime('%d/%m/%Y')} " \
                    + f"et le {cover_document['arrival_date'].strftime('%d/%m/%Y')}"
            }
            second_field_to_append = {
                "api_key": f"mare_{disease}",
                "value": "Oui"
            }
            placeholder_fields.append(first_field_to_append)
            placeholder_fields.append(second_field_to_append)
        except KeyError:
            first_field_to_append = {
                "api_key": f"mare_{disease}_test_date",
                "value": "néant"
            }
            second_field_to_append = {
                "api_key": f"mare_{disease}",
                "value": "Non"
            }
            placeholder_fields.append(first_field_to_append)
            placeholder_fields.append(second_field_to_append)

    for vaccine in ["rhino", "grippe", "tetanos"]:
        # for the stallion
        placeholder_fields.append({
            "api_key": f"stallion_{vaccine}",
            "value": "Oui" if vaccine in cover_document["stallion_vaccines"] else "Non"
        })

        # for the mare
        placeholder_fields.append({
            "api_key": f"mare_{vaccine}",
            "value": "Oui" if vaccine in cover_document["cover_specs"]["demanded_vaccines"] else "Non"
        })

    data = {
        "template_id": template_id,
        "test": test,
        "title": "Contrat de saillie",
        "locale": "fr",
        "expires_in_hours": expires_in_hours,
        "labels": [cover_document["cover_type"].upper()],
        "signers": signers,
        "placeholder_fields": placeholder_fields,
        "emails": {
            "cc_email_addresses": config['cc_email_addresses'],
            "signature_request_subject": "Votre contrat de saillie est prêt pour signature",
            "signature_request_text": "Bonjour __FULL_NAME__,\n\nPour vérifier et signer votre contrat de saillie, cliquez sur le bouton ci-dessous.",
            "final_contract_subject": "La signature de votre document est terminée",
            "final_contract_text": "Bonjour __FULL_NAME__,\n\nLa signature de votre document est terminée.\n\nMerci pour votre confiance."
        }
    }

    async with aiohttp.ClientSession() as session:
        url = f"{esignatures_contracts_api_url}?token={token}"
        async with session.post(url, json=data) as response:
            json_to_return = await response.json()
            assert response.status == 200, f"POST on {esignatures_contracts_api_url}?token={token} : received status {response.status} with json {json_to_return}"

            return json_to_return, data
