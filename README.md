# FotoMir - Sincronizador de Metadados de Imagens com IA

Este projeto utiliza a API Gemini do Google para analisar imagens armazenadas no Google Cloud Storage, extrair tags descritivas, traduzi-las para o português e salvar esses metadados no Firestore. O script é projetado para sincronizar o estado do Firestore com o do Storage, processando novas imagens e removendo metadados de imagens deletadas.

## Funcionalidades

- Lista imagens em um bucket do Google Cloud Storage.
- Utiliza o modelo `gemini-1.5-flash` para gerar tags descritivas para cada imagem.
- Traduz as tags de inglês para português usando a Google Translate API.
- Salva os metadados (tags, nome do arquivo, etc.) no Google Cloud Firestore.
- Sincroniza o Firestore, removendo metadados de imagens que não existem mais no Storage.

## Configuração do Ambiente

Siga os passos abaixo para configurar e executar o projeto.

### 1. Pré-requisitos

- Python 3.8+
- Uma conta no Google Cloud com um projeto ativo.
- APIs habilitadas no seu projeto Google Cloud:
  - Vertex AI API (para o Gemini)
  - Cloud Storage API
  - Cloud Firestore API
  - Cloud Translation API
- Um arquivo de credenciais de conta de serviço (`.json`) com as permissões necessárias (ex: `Vertex AI User`, `Cloud Datastore User`, `Storage Object Viewer`).

### 2. Instalação

Clone o repositório e instale as dependências:

```bash
git clone https://github.com/seu-usuario/fotoMir.git
cd fotoMir
pip install -r requirements.txt
```

### 3. Variáveis de Ambiente

Crie um arquivo chamado `.env` na raiz do projeto e adicione as seguintes variáveis, substituindo pelos seus valores:

```
GOOGLE_APPLICATION_CREDENTIALS="caminho/para/seu/arquivo-de-credenciais.json"
BUCKET_NAME="nome-do-seu-bucket"
BUCKET_FOLDER_PATH="fotos/" # Opcional: caminho da pasta dentro do bucket
```

### 4. Execução

Para iniciar o script de sincronização, execute:

```bash
python main.py
```
