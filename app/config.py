from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List

_APP_DIR = Path(__file__).parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_APP_DIR.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='allow'
    )

    # company
    company_name: str = "Le Repaire de l'Étalon"

    # frontend
    frontend_url: str = "https://lerepairedeletalon.alexandrevenot.ovh"

    # esignatures
    esignatures_url: str = "https://esignatures.io"
    send_demo_contracts: bool = True

    # database
    db_to_use: str = "test"
    mongo_url: str = "mongodb-25a50afa-of01ab2eb.database.cloud.ovh.net"

    # obj storage
    stallion_photos_bucket_name: str = "lerepairedeletalon-public"

    # auth
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 180

    # contracts
    contracts_templates_ids: Dict[str, str] = {
        "lib": "0aa1fe35-9342-4381-b2f5-21c1e03c31eb",
        "hand": "0aa1fe35-9342-4381-b2f5-21c1e03c31eb"
    }
    esignatures_contracts_api_url: str = "https://esignatures.io/api/contracts"
    signature_request_links_expiration_delay_hours: int = 8760 # one year
    signature_request_delivery_methods: List[str] = []
    signed_document_delivery_method: str = "email"
    multi_factor_authentications: List[str] = ["sms_verification_code"]
    cc_email_addresses: List[str] = ["alexandre.venot.lrde@gmail.com"]
    cover_technique_names: Dict[str, str] = {
        "lib": "Monte en liberté",
        "hand": "Monte en main"
    }

    # covers
    buyer_status_graph: Dict[str, List[str]] = {
        "requested": [],
        "approved": ["signingstarted"],
        "signingstarted": [],
        "buyersigned": [],
        "sellersigned": [],
        "downpaid": [],
        "fullypaid": [],
        "denied": []
    }
    seller_status_graph: Dict[str, List[str]] = {
        "requested": ["denied", "approved"],
        "approved": ["requested"],
        "signingstarted": [],
        "buyersigned": [],
        "sellersigned": [],
        "downpaid": [],
        "fullypaid": [],
        "denied": ["requested"]
    }
    status: List[str] = [
        "requested",
        "approved",
        "signingstarted",
        "buyersigned",
        "sellersigned",
        "downpaid",
        "fullypaid",
        "denied"
    ]
    groups: Dict[str, List[str]] = {
        "denied": ["denied"],
        "pendingApproval": ["requested", "approved"],
        "pendingSignature": ["signingstarted", "buyersigned", "sellersigned"],
        "onGoing": ["downpaid"],
        "done": ["fullypaid"]
    }
    destination_pov_and_status_to_group: Dict[str, Dict[str, str]] = {
        "seller": {
            "requested": "pendingApproval",
            "buyersigned": "pendingSignature",
            "downpaid": "onGoing",
            "fullypaid": "done"
        },
        "buyer": {
            "denied": "denied",
            "approved": "pendingApproval",
            "sellersigned": "pendingSignature",
            "requested": "pendingApproval"
        }
    }

    # mailing
    logo_filename: str = "logo-black.png"
    declared_sender_email: str = "noreply@lerepairedeletalon.com"
    email_verification_route: str = "/email-verification"
    password_update_page: str = "/password-update"
    smtp_server_name: str = "ssl0.ovh.net"
    smtp_server_port_out: int = 587

    # payments
    fees_coeff: float = 0.08

    # stallions
    photo_max_size: int = 4194304 # 4Mo
    photo_low_res_width: int = 720 # pixels
    allowed_photos_content_types: List[str] = [
        "image/jpeg",
        "image/jpg",
        "image/png"
    ]
    cover_types: List[str] = ["lib", "hand"]
    onsite_cover_types: List[str] = ["lib", "hand"]
    remote_cover_types: List[str] = []
    balance_payment_conditions: List[str] = [
        "covered",
        "covered_1_10",
        "living_foal",
        "living_foal_48"
    ]
    advance_min_percentage_value: int = 15
    advance_max_percentage_value: int = 50
    available_std_tests: List[str] = ["metrite", "arterite", "anemie"]
    minimum_std_test_oldness: int = 1
    maximum_std_test_oldness: int = 180
    available_vaccines: List[str] = ["rhino", "grippe", "tetanos"]
    profile_statuses: List[str] = ["to_be_validated", "hidden", "visible"]
    cover_minimum_price: int = 10

    # users
    allowed_bank_identity_file_content_types: List[str] = [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/pdf"
    ]

settings = Settings()