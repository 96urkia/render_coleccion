# Gestión de la Colección — Web app propia (backend + frontend)

Reimplementación del `app.py` de Streamlit como una aplicación web independiente:

- **`backend/main.py`** — API en FastAPI. Contiene, sin cambios de lógica, todo el
  procesamiento de `app.py` original (parseo de los `.txt`, clasificación por
  signatura/CDU, recomendaciones por similitud de coseno, consultas SQL a la red).
- **`frontend/`** — HTML + CSS + JS propios (sin Streamlit ni ningún framework de
  componentes), con diseño de fichero de biblioteca.
- Todo se empaqueta en **un único contenedor Docker** que sirve la API en `/api/*`
  y el frontend estático en `/`.

## 1. Probar en local (opcional)

```bash
docker compose up --build
```

Abre `http://localhost:8000`.

## 2. Desplegar en una VM Oracle Cloud Free Tier

### 2.1 Crear la instancia
1. En Oracle Cloud Console → **Compute → Instances → Create Instance**.
2. Elige forma **VM.Standard.A1.Flex** (ARM, Always Free) — asigna, por ejemplo,
   2 OCPU / 8 GB RAM (puedes llegar hasta 4 OCPU / 24 GB sin coste).
3. Imagen: Ubuntu 24.04.
4. Añade tu clave SSH pública.
5. En **Networking**, asegúrate de que la VCN tiene una regla de entrada para el
   puerto 8000 (o 80/443 si vas a poner Nginx delante) en el *Security List* o
   *Network Security Group*.

### 2.2 Conectar y preparar la VM

```bash
ssh ubuntu@<IP_PUBLICA_DE_TU_VM>

# Docker
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
newgrp docker
```

### 2.3 Abrir el puerto también en el firewall interno de la VM (iptables/netfilter)

Las imágenes de Oracle traen un firewall interno activo:

```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save   # si está instalado; si no, instala iptables-persistent
```

### 2.4 Subir el proyecto y levantarlo

```bash
git clone <tu-repo-con-este-proyecto> gestion-coleccion-web
cd gestion-coleccion-web
docker compose up -d --build
```

La primera petición que necesite la base de datos de red (pestaña de
Recomendaciones) descargará los ~500 MB desde Dropbox en segundo plano; puedes
comprobar el estado con:

```bash
curl http://localhost:8000/api/estado
```

### 2.5 (Recomendado) Nginx + HTTPS delante

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Configura `/etc/nginx/sites-available/gestion-coleccion`:

```nginx
server {
    listen 80;
    server_name tu-dominio.ejemplo;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/gestion-coleccion /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d tu-dominio.ejemplo
```

Si usas Nginx con dominio, ya no necesitas exponer el 8000 al exterior: cierra
ese puerto en el Security List y deja solo 80/443.

## 3. Notas sobre persistencia

- La base de datos de red (`gestion_coleccion.db`, ~500 MB) se guarda en el
  volumen Docker `db_data`, así que sobrevive a reinicios del contenedor.
- Los análisis que suben los usuarios (topográfico/catálogo) se mantienen
  **en memoria** del proceso durante 3 horas (`SESSION_TTL_SECONDS` en
  `main.py`). Si reinicias el contenedor, hay que volver a subir los archivos
  — es intencional, ya que esos ficheros no se persisten en disco por defecto.

## 4. Variables de entorno útiles

| Variable | Por defecto | Descripción |
|---|---|---|
| `DB_URL` | URL de Dropbox original | Origen de la base de datos de red |
| `DB_PATH` | `/data/gestion_coleccion.db` | Ruta local de la base de datos |
| `FRONTEND_DIR` | `/app/frontend` | Carpeta servida como estático |

## 5. Actualizar el diseño o los filtros

- Todo el HTML está en `frontend/index.html`, sin ninguna dependencia de
  Streamlit ni de ningún framework de componentes — puedes tocar el
  marcado libremente.
- La identidad visual (colores, tipografías, tarjetas de fichero) está
  centralizada en `frontend/styles.css` bajo `:root`.
- Las llamadas a la API y el renderizado de tablas/gráficas están en
  `frontend/app.js`.
