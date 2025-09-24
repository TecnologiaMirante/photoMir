from datetime import datetime, timezone
from google.cloud import firestore
from typing import Set, Dict, Any, List
# A Vision API não será mais usada, então a importação é removida
# from google.cloud import vision
from google.cloud import translate_v2 as translate
from google.cloud import storage 
from dotenv import load_dotenv
import os
import io

# Importações para o Gemini
import google.generativeai as genai
from PIL import Image

# Importação da biblioteca de autenticação
import google.oauth2.service_account

load_dotenv()

# --- CONFIGURAÇÕES ---

SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
BUCKET_NAME = os.getenv('BUCKET_NAME')
BUCKET_FOLDER_PATH = os.getenv('BUCKET_FOLDER_PATH', '')
FIRESTORE_DATABASE = os.getenv('FIRESTORE_DATABASE', 'acervo-fotos-ia')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
GEMINI_PROMPT = "Analyze this image and provide a list of descriptive tags in English, separated by commas. Focus on objects, scenes, and key attributes. Return only the tags, nothing else."


# --- INICIALIZAÇÃO DOS CLIENTES ---

SCOPES = [
    # O escopo da Vision API é removido
    # 'https://www.googleapis.com/auth/cloud-vision',
    'https://www.googleapis.com/auth/datastore',
    'https://www.googleapis.com/auth/cloud-translation',
    'https://www.googleapis.com/auth/devstorage.read_only',
    'https://www.googleapis.com/auth/cloud-platform' # Escopo amplo que inclui Vertex AI/Gemini
]

# A biblioteca do Gemini usará automaticamente as credenciais da conta de serviço
# definidas em GOOGLE_APPLICATION_CREDENTIALS, então a configuração explícita com API Key é removida.

if not SERVICE_ACCOUNT_FILE:
    raise ValueError("A variável de ambiente 'GOOGLE_APPLICATION_CREDENTIALS' não foi definida no arquivo .env.")

if not BUCKET_NAME:
    raise ValueError("A variável de ambiente 'BUCKET_NAME' não foi definida no arquivo .env.")


creds = google.oauth2.service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Clientes das APIs
storage_client = storage.Client(credentials=creds)
# O cliente da Vision API é removido
# vision_client = vision.ImageAnnotatorClient(credentials=creds)
translate_client = translate.Client(credentials=creds)
db = firestore.Client(database=FIRESTORE_DATABASE, credentials=creds)

# NOVO: Inicializa o modelo Gemini uma única vez para reutilização
gemini_model = genai.GenerativeModel(GEMINI_MODEL)

# --- FUNÇÕES ---

def list_images_in_bucket(bucket_name: str, folder_path: str) -> Set[str]:
    """Lista os arquivos de imagem em uma pasta do Cloud Storage."""
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=folder_path)

    files = set()
    for blob in blobs:
        if blob.name.endswith(('.jpg', '.jpeg', '.png')):
            if blob.name != folder_path:
                files.add(os.path.basename(blob.name))
    return files


def get_image_metadata(file_name_with_path: str) -> Dict[str, Any]:
    """Baixa uma imagem e envia para a Gemini API para extrair metadados e traduzir."""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name_with_path)
    file_content = io.BytesIO(blob.download_as_bytes())

    # Prepara a imagem para o Gemini
    img = Image.open(file_content)
    
    # Chama a Gemini API (reutilizando o modelo inicializado)
    try:
        response = gemini_model.generate_content([GEMINI_PROMPT, img])
    except Exception as e:
        # Captura erros específicos da API para não parar o loop principal
        print(f"      -> ERRO na chamada da API Gemini: {e}")
        # Retorna um dicionário de erro para que o loop principal possa continuar
        # ou lança a exceção se preferir parar o processo.
        raise
    
    # Extrai e limpa as tags da resposta do Gemini
    all_tags_en = []
    if response.text:
        gemini_tags_text = response.text
        all_tags_en = [tag.strip() for tag in gemini_tags_text.split(',') if tag.strip()]

    # Traduz as tags para o português
    all_tags_pt: List[str] = []
    if all_tags_en:
        translations = translate_client.translate(all_tags_en, target_language='pt')
        all_tags_pt = [t['translatedText'] for t in translations]

    doc_id = os.path.basename(file_name_with_path)

    return {
        "file_id": doc_id,
        "file_name": file_name_with_path,
        "tags_en": all_tags_en,
        "tags_pt": all_tags_pt,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

def save_metadata_to_firestore(metadata: Dict[str, Any]) -> None:
    """Salva os metadados de uma imagem no Firestore."""
    doc_id = metadata['file_id']
    doc_ref = db.collection('images').document(doc_id)
    doc_ref.set(metadata)
    print(f"   -> Metadados salvos no Firestore para o documento: {doc_id}")

def main():
    """Função principal para orquestrar o processo de sincronização."""
    print(f"Iniciando o processo de sincronização de metadados (Modelo: {GEMINI_MODEL})...")

    storage_image_ids = list_images_in_bucket(BUCKET_NAME, BUCKET_FOLDER_PATH)

    try:
        firestore_doc_ids = {doc.id for doc in db.collection('images').stream()}
    except Exception as e:
        print(f"Erro ao acessar o Firestore: {e}")
        return

    deleted_image_ids = firestore_doc_ids - storage_image_ids
    if deleted_image_ids:
        print(f"\nExcluindo {len(deleted_image_ids)} metadados de fotos removidas do Cloud Storage...")
        for file_id in deleted_image_ids:
            try:
                db.collection('images').document(file_id).delete()
                print(f"   -> Metadados excluídos do Firestore para o documento: {file_id}")
            except Exception as e:
                print(f"   -> ERRO ao excluir o metadado {file_id}: {e}")
    else:
        print("\nNenhuma foto foi removida do Cloud Storage.")

    new_image_ids = storage_image_ids - firestore_doc_ids
    
    if new_image_ids:
        print(f"\n{len(new_image_ids)} novas imagens serão processadas.")
        print("\nIniciando processamento...")
        
        for i, file_id in enumerate(new_image_ids, 1):
            file_name_with_path = f"{BUCKET_FOLDER_PATH}{file_id}"
            print(f"Processando imagem {i}/{len(new_image_ids)}: {file_name_with_path}")
            try:
                metadata = get_image_metadata(file_name_with_path)
                save_metadata_to_firestore(metadata)
            except Exception as e:
                print(f"   -> ERRO ao processar o arquivo {file_name_with_path}: {e}")
    else:
        print("\nNenhuma nova imagem adicionada para ser processada.")

    print(f"\nProcesso de sincronização concluído!")

if __name__ == '__main__':
    main()