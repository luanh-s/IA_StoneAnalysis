
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.faiss_index import FaissRAG
from app.salesforce_client import buscar_contato_e_veiculos
from app.salesforce_client import buscar_cliente_e_pedidos
import requests, logging, os
import openai

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Configuração correta de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pode ser restringido para ["http://localhost"] em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa FaissRAG
rag = FaissRAG()
with open("data/articles.txt", "r", encoding="utf-8") as f:
    for artigo in f.read().split("\n---\n"):
        rag.adicionar_texto(artigo.strip())

# Configuração da chave da OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")  # Ou defina diretamente: openai.api_key = "sua-chave-aqui"

def consultar_llama(prompt):
    try:
        res = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        })
        res.raise_for_status()
        return res.json()["response"]
    except Exception as e:
        logging.error(f"Error querying LLaMA: {str(e)}")
        return "Error generating response with local LLaMA."

def consultar_chatgpt(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Error querying ChatGPT: {str(e)}")
        return "Error generating response with ChatGPT."

@app.post("/ask")
async def ask_agent(request: Request):
    data = await request.json()
    pergunta = data.get("message", "")
    modelo = data.get("modelo", "chatgpt")  # "chatgpt" é o padrão
    account_id = data.get("account_id", None)

    # contextos = rag.consultar(pergunta)

    contexto_cliente = ""
    if account_id:
        try:
            cliente = buscar_cliente_e_pedidos(account_id)
            logging.info(f"cliente: {repr(cliente)}")
            if cliente:
                contexto_cliente += f"Customer: {cliente.get('nome', 'Unknown')}\n"

                pedidos = cliente.get("pedidos", [])
                if pedidos:
                    contexto_cliente += "Orders:\n"
                    for ped in pedidos:
                        contexto_cliente += (
                            f"- {ped.get('TotalAmount', 'Unknown TotalAmount')} "
                            f"{ped.get('Descricao_Draft__c', 'Unknown Descricao_Draft__c')}\n"
                        )
                else:
                    contexto_cliente += "No Orders found.\n"

                contexto_cliente += "\n"

        except Exception as e:
            logging.warning(f"Error retrieving user data: {e}")
            contexto_cliente += "Error retrieving user data.\n\n"

    prompt = f"{contexto_cliente}The customer asked: \"{pergunta}\"\n\n"
    prompt += "Based on the following technical articles:\n"
    # prompt += "\n".join(f"- {c}" for c in contextos)
    prompt += "\n\nPlease respond clearly and objectively."
    prompt += "\n\nPlease keep the responses under 300 characters."

    logging.info(f"prompt: {prompt}")
    
    if modelo == "chatgpt":
        resposta = consultar_chatgpt(prompt)
    else:
        resposta = consultar_llama(prompt)

    return {"resposta": resposta}
