# Ocean Viking Rescues - Deployment Guide

Complete guide for deploying on Infomaniak Cloud Server.

## Prerequisites

- Infomaniak Cloud Server (VPS) or Web Hosting
- SSH access to your server
- Domain name configured in Infomaniak DNS

## Deployment Methods

### ⭐ Recommended: Infomaniak Port Redirection (Simplest)

If using Infomaniak Cloud Server, you can use their built-in port redirection feature instead of configuring Nginx. This is the **easiest and recommended method**.

#### Configure Infomaniak Port Redirection

1. Log in to [Infomaniak Manager](https://manager.infomaniak.com/)
2. Go to your Cloud Server
3. Navigate to **Network** → **Port Redirection**
4. Add new redirection:
   - **External Port**: 80 (HTTP)
   - **Internal Port**: 8000
   - **Protocol**: TCP
5. Add another for HTTPS:
   - **External Port**: 443 (HTTPS)
   - **Internal Port**: 8000
   - **Protocol**: TCP
6. Save and apply

#### Deploy Application (Without Nginx)

```bash
# Upload files
scp -r * username@your-server:/var/www/ocean-viking-rescues/

# SSH into server
ssh username@your-server
cd /var/www/ocean-viking-rescues

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env  # Add your credentials

# Set up systemd service
sudo cp ocean-viking.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ocean-viking
sudo systemctl start ocean-viking

# Check status
sudo systemctl status ocean-viking
```

✅ **That's it!** Your app is now accessible at `http://your-domain.com`

For SSL/HTTPS, configure it in Infomaniak Manager under SSL Certificates.

---

### Alternative: Traditional Nginx Setup

If you prefer traditional setup or need more control, use Nginx as reverse proxy:

## Quick Deployment (Automated with Nginx)

### 1. Upload Files to Server

```bash
# From your local machine
scp -r * username@your-server-ip:/var/www/ocean-viking-rescues/
```

### 2. Run Deployment Script

```bash
# SSH into your server
ssh username@your-server-ip

# Make script executable
cd /var/www/ocean-viking-rescues
chmod +x deploy.sh

# Run deployment (replace with your domain)
sudo ./deploy.sh your-domain.com
```

### 3. Configure Environment Variables

```bash
sudo nano /var/www/ocean-viking-rescues/.env
```

Add all your environment variables:
```env
PASSWORD=your_secure_password
TOKEN=your_kobo_token
ASSET=your_asset_id
ASSETMEDEVAC=medevac_asset_id
ASSETDISEMBARK=disembark_asset_id
GOOGLESHEETID=your_google_sheet_id
GOOGLESERVICEACCUNT={"type":"service_account",...}
CONNECTION=your_azure_connection_string
LOGICAPPTRIGGER=your_logic_app_url
```

### 4. Set up SSL (HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Manual Deployment

### Step 1: Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv nginx
```

### Step 2: Application Setup

```bash
# Create directory
sudo mkdir -p /var/www/ocean-viking-rescues
cd /var/www/ocean-viking-rescues

# Upload your files (from local machine)
# scp -r * username@server:/var/www/ocean-viking-rescues/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Systemd Service

```bash
# Copy service file
sudo cp ocean-viking.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ocean-viking
sudo systemctl start ocean-viking

# Check status
sudo systemctl status ocean-viking
```

### Step 4: Configure Nginx

```bash
# Copy nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/ocean-viking

# Update domain name in config
sudo nano /etc/nginx/sites-available/ocean-viking
# Replace 'your-domain.com' with actual domain

# Enable site
sudo ln -s /etc/nginx/sites-available/ocean-viking /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Step 5: Configure Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

### Step 6: Set Permissions

```bash
sudo chown -R www-data:www-data /var/www/ocean-viking-rescues
sudo chmod -R 755 /var/www/ocean-viking-rescues
```

## Docker Deployment (Alternative)

### Using Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose

# Build and run
cd /var/www/ocean-viking-rescues
sudo docker-compose up -d

# View logs
sudo docker-compose logs -f
```

### Configure Nginx as Reverse Proxy

Update nginx.conf to proxy to Docker container:
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    ...
}
```

## Infomaniak-Specific Configuration

### DNS Configuration

1. Log in to Infomaniak Manager
2. Go to Domain > DNS Zone
3. Add A record pointing to your server IP:
   - Type: A
   - Name: @ (or subdomain)
   - Value: Your server IP
   - TTL: 3600

### Port Redirection (Recommended Method)

See: https://www.infomaniak.com/en/support/faq/2171/redirect-web-traffic-to-a-specific-port

1. Go to Infomaniak Manager → Cloud Server → Network
2. Add Port Redirection:
   - External: 80 → Internal: 8000 (HTTP)
   - External: 443 → Internal: 8000 (HTTPS)
3. Your application will be directly accessible without Nginx

### SSL Certificate

#### Option 1: Infomaniak SSL (with Port Redirection)
1. Go to Infomaniak Manager → Cloud Server → SSL Certificates
2. Enable and configure SSL certificate
3. SSL will be automatically applied to port 443 traffic redirected to your app

#### Option 2: Let's Encrypt (with Nginx)
```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Auto-renewal is configured automatically.

## Maintenance Commands

### View Logs

```bash
# Application logs
sudo journalctl -u ocean-viking -f

# Nginx access logs
sudo tail -f /var/log/nginx/ocean-viking-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/ocean-viking-error.log
```

### Restart Services

```bash
# Restart application
sudo systemctl restart ocean-viking

# Reload Nginx (without downtime)
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx
```

### Update Application

```bash
# Upload new code
scp -r * username@server:/var/www/ocean-viking-rescues/

# Activate venv and update dependencies
cd /var/www/ocean-viking-rescues
source venv/bin/activate
pip install -r requirements.txt

# Restart application
sudo systemctl restart ocean-viking
```

### Monitor Resources

```bash
# CPU and Memory usage
htop

# Disk usage
df -h

# Check application status
sudo systemctl status ocean-viking
```

## Troubleshooting

### Application won't start

```bash
# Check logs for errors
sudo journalctl -u ocean-viking -n 50

# Check if port 8000 is in use
sudo lsof -i :8000

# Test application manually
cd /var/www/ocean-viking-rescues
source venv/bin/activate
gunicorn --config gunicorn_config.py wsgi:app
```

### Nginx 502 Bad Gateway

```bash
# Check if application is running
sudo systemctl status ocean-viking

# Check Nginx error logs
sudo tail -f /var/log/nginx/ocean-viking-error.log

# Verify proxy settings in nginx.conf
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R www-data:www-data /var/www/ocean-viking-rescues

# Fix permissions
sudo chmod -R 755 /var/www/ocean-viking-rescues
```

### Environment Variables Not Loading

```bash
# Check .env file exists
ls -la /var/www/ocean-viking-rescues/.env

# Verify service file references .env
cat /etc/systemd/system/ocean-viking.service

# Reload service
sudo systemctl daemon-reload
sudo systemctl restart ocean-viking
```

## Security Checklist

- [ ] SSL/HTTPS enabled via Let's Encrypt
- [ ] Strong passwords in .env file
- [ ] Firewall configured (UFW)
- [ ] Regular system updates scheduled
- [ ] Nginx security headers configured
- [ ] File permissions set correctly (755 directories, 644 files)
- [ ] .env file not publicly accessible
- [ ] Regular backups configured
- [ ] Monitor logs for suspicious activity

## Backup Strategy

### Manual Backup

```bash
# Backup application and data
sudo tar -czf ocean-viking-backup-$(date +%Y%m%d).tar.gz \
  /var/www/ocean-viking-rescues

# Backup to remote location
scp ocean-viking-backup-*.tar.gz user@backup-server:/backups/
```

### Automated Backup (Cron)

```bash
# Edit crontab
sudo crontab -e

# Add daily backup at 2 AM
0 2 * * * /usr/local/bin/backup-ocean-viking.sh
```

## Performance Optimization

### Gunicorn Workers

Adjust in `gunicorn_config.py`:
```python
workers = (2 * cpu_count) + 1
```

### Nginx Caching

Add to nginx.conf:
```nginx
location /static {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

## Support

- Server logs: `/var/log/nginx/` and `journalctl -u ocean-viking`
- Infomaniak support: https://www.infomaniak.com/support
- Application issues: Check environment variables and Kobo API connectivity

## Additional Resources

- [Infomaniak Cloud Documentation](https://www.infomaniak.com/en/support/faq)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
