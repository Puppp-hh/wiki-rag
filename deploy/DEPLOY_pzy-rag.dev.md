# Deploy Wiki-RAG to `pzy-rag.dev`

This deployment assumes:

- Ubuntu 22.04 / 24.04 server
- Domain: `pzy-rag.dev`
- App path: `/opt/wiki-rag`
- FastAPI listens on `127.0.0.1:8000`
- Nginx serves React static files and proxies `/api`
- Ollama runs on the same server

## 1. Recommended Server

For `deepseek-r1:1.5b` + `nomic-embed-text`:

| Spec | Result |
|---|---|
| 2 vCPU / 4GB RAM | OK for testing, may be tight when indexing or uploading large docs |
| 2 vCPU / 8GB RAM | Recommended for a smoother personal deployment |
| 4 vCPU / 8GB RAM | Better, but consumes free trial hours faster |

Use **Ubuntu 22.04 64-bit**. Avoid Windows Server for this project.

## 2. DNS

Create DNS records:

```text
Type: A
Host: @
Value: your_server_public_ip

Type: A
Host: www
Value: your_server_public_ip
```

`.dev` domains require HTTPS in modern browsers, so Certbot HTTPS is mandatory.

## 3. Install System Packages

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-pip python3-venv curl certbot python3-certbot-nginx apache2-utils
```

Install Node.js 20:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 4. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

Check:

```bash
ollama list
```

## 5. Clone and Build

```bash
cd /opt
sudo git clone https://github.com/Puppp-hh/wiki-rag.git wiki-rag
sudo chown -R $USER:$USER /opt/wiki-rag
cd /opt/wiki-rag

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env

cd web-frontend
npm install
npm run build
```

## 6. Permissions

The systemd service runs as `www-data`, so give it access to app data:

```bash
sudo chown -R www-data:www-data /opt/wiki-rag
sudo chmod -R u+rwX /opt/wiki-rag/data /opt/wiki-rag/cache
```

## 7. FastAPI Service

```bash
sudo cp /opt/wiki-rag/deploy/systemd/wiki-rag-api.service /etc/systemd/system/wiki-rag-api.service
sudo systemctl daemon-reload
sudo systemctl enable wiki-rag-api
sudo systemctl start wiki-rag-api
sudo systemctl status wiki-rag-api
```

## 8. Nginx

Create Basic Auth user:

```bash
sudo htpasswd -c /etc/nginx/.wiki_rag_passwd pzy
```

Install Nginx config:

```bash
sudo cp /opt/wiki-rag/deploy/nginx/pzy-rag.dev.conf /etc/nginx/sites-available/wiki-rag
sudo ln -s /etc/nginx/sites-available/wiki-rag /etc/nginx/sites-enabled/wiki-rag
sudo nginx -t
sudo systemctl reload nginx
```

## 9. HTTPS

Because `.dev` is HTTPS-only in browsers:

```bash
sudo certbot --nginx -d pzy-rag.dev -d www.pzy-rag.dev
```

Open:

```text
https://pzy-rag.dev
```

## 10. Update Deployment Later

```bash
cd /opt/wiki-rag
sudo -u www-data git pull

sudo -u www-data /opt/wiki-rag/.venv/bin/pip install -r requirements.txt

cd web-frontend
sudo -u www-data npm install
sudo -u www-data npm run build

sudo systemctl restart wiki-rag-api
sudo systemctl reload nginx
```
