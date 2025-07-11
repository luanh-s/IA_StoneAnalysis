import os
# import json
import logging
import requests
from dotenv import load_dotenv
# from threading import Lock

load_dotenv()

SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET")
SF_ENDPOINT = os.getenv("SF_ENDPOINT")
SF_API_VERSION = "v60.0"

CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# cache_lock = Lock()

def autenticar_salesforce():
    url = SF_ENDPOINT + "/services/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SF_CLIENT_ID,
        "client_secret": SF_CLIENT_SECRET
    }
    logging.info("Autenticando com client_credentials...")
    res = requests.post(url, data=data)
    res.raise_for_status()
    auth = res.json()
    logging.info("Token recebido com sucesso.")
    return auth["access_token"], auth["instance_url"]

def buscar_contato_e_veiculos(contact_id):
    cache_path = os.path.join(CACHE_DIR, f"{contact_id}.json")
    try:
        token, instance_url = autenticar_salesforce()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        soql_contato = f"SELECT Id, Name, AccountId FROM Contact WHERE Id = '{contact_id}' OR Id IN (SELECT ContactId FROM User WHERE Id = '{contact_id}')"
        url_query = f"{instance_url}/services/data/{SF_API_VERSION}/query"
        res = requests.get(url_query, headers=headers, params={"q": soql_contato})
        res.raise_for_status()
        contato_data = res.json()["records"]
        if not contato_data:
            raise ValueError("Contato não encontrado.")
        contato = contato_data[0]
        account_id = contato.get("AccountId")

        vehicles = []
        if account_id:
            soql_vehicles = f"SELECT Id, Name, ChassisNumber, MakeName, ModelName, ModelYear FROM Vehicle WHERE CurrentOwnerId = '{account_id}'"
            res2 = requests.get(url_query, headers=headers, params={"q": soql_vehicles})
            res2.raise_for_status()
            vehicles = [
                {
                    "name": v.get("Name"),
                    "vin": v.get("ChassisNumber"),
                    "make": v.get("MakeName"),
                    "model": v.get("ModelName"),
                    "year": v.get("ModelYear")
                }
                for v in res2.json()["records"]
            ]
            logging.info(f"[{contact_id}] Veículos retornados: {vehicles}")

        dados = {"nome": contato.get("Name"), "account_id": account_id, "veiculos": vehicles}

        # Salvar com lock
        # with cache_lock:
        #     with open(cache_path, "w", encoding="utf-8") as f:
        #         json.dump(dados, f, ensure_ascii=False, indent=2)
        # logging.info(f"[{contact_id}] Dados salvos em cache.")

        return dados

    except Exception as e:
        logging.warning(f"[{contact_id}] Erro Salesforce: {e}")
        # if os.path.exists(cache_path):
        #     logging.info(f"[{contact_id}] Usando cache local.")
            # with open(cache_path, "r", encoding="utf-8") as f:
            #     return json.load(f)
        # logging.error(f"[{contact_id}] Sem dados em cache.")
        return None


def buscar_cliente_e_pedidos(account_id):
    try:
        token, instance_url = autenticar_salesforce()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        soql_cliente = f"SELECT Id, Name FROM Account WHERE Id = '{account_id}'"
        url_query = f"{instance_url}/services/data/{SF_API_VERSION}/query"
        res = requests.get(url_query, headers=headers, params={"q": soql_cliente})
        res.raise_for_status()
        cliente_data = res.json()["records"]
        if not cliente_data:
            raise ValueError("Cliente não encontrado.")
        cliente = cliente_data[0]

        soql_orders = f"SELECT Id, Name, TotalAmount, Descricao_Draft__c FROM Order WHERE AccountId = '{account_id}'"
        res2 = requests.get(url_query, headers=headers, params={"q": soql_orders})
        res2.raise_for_status()

        orders_data = res2.json()["records"]
        logging.info(f"[{account_id}] Pedidos retornados: {orders_data}")

        dados = {"nome": cliente.get("Name"), "account_id": account_id, "pedidos": orders_data}
        return dados

    except Exception as e:
        logging.warning(f"[{account_id}] Erro Salesforce: {e}")
        # if os.path.exists(cache_path):
        #     logging.info(f"[{account_id}] Usando cache local.")
            # with open(cache_path, "r", encoding="utf-8") as f:
            #     return json.load(f)
        # logging.error(f"[{account_id}] Sem dados em cache.")
        return None

def busca_salesforce(query):
    token, instance_url = autenticar_salesforce()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    url_query = f"{instance_url}/services/data/{SF_API_VERSION}/query"
    res = requests.get(url_query, headers=headers, params={"q": query})
    res.raise_for_status()
    query_data = res.json()["records"]
    if not query_data:
        raise ValueError("Cliente não encontrado.")
    return query_data