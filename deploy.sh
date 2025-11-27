#!/bin/bash

# Ocean Viking Rescues - Deployment Script for Infomaniak Cloud Server
# This script automates the deployment process

set -e  # Exit on error

echo "=========================================="
echo "Ocean Viking Rescues - Deployment Script"
echo "=========================================="

# Configuration
APP_DIR="/var/www/ocean-viking-rescues"
SERVICE_NAME="ocean-viking"
NGINX_SITE="ocean-viking"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Step 1: Update system
echo -e "${YELLOW}[1/9] Updating system packages...${NC}"
apt update && apt upgrade -y

# Step 2: Install dependencies
echo -e "${YELLOW}[2/9] Installing dependencies...${NC}"
apt install -y python3 python3-pip python3-venv nginx curl

# Step 3: Create application directory
echo -e "${YELLOW}[3/9] Creating application directory...${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

# Step 4: Set up virtual environment
echo -e "${YELLOW}[4/9] Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Step 5: Install Python packages
echo -e "${YELLOW}[5/9] Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Step 6: Set permissions
echo -e "${YELLOW}[6/9] Setting permissions...${NC}"
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Step 7: Set up systemd service
echo -e "${YELLOW}[7/9] Setting up systemd service...${NC}"
cp ocean-viking.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# Step 8: Configure Nginx
echo -e "${YELLOW}[8/9] Configuring Nginx...${NC}"
cp nginx.conf /etc/nginx/sites-available/$NGINX_SITE

# Replace placeholder with actual domain if provided
if [ ! -z "$1" ]; then
    sed -i "s/your-domain.com/$1/g" /etc/nginx/sites-available/$NGINX_SITE
    echo -e "${GREEN}Configured for domain: $1${NC}"
else
    echo -e "${YELLOW}No domain provided. Please edit /etc/nginx/sites-available/$NGINX_SITE manually${NC}"
fi

ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Step 9: Set up firewall
echo -e "${YELLOW}[9/9] Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow 'Nginx Full'
    ufw allow OpenSSH
    ufw --force enable
fi

# Check service status
echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
systemctl status $SERVICE_NAME --no-pager
echo ""
echo -e "${GREEN}Application is running!${NC}"
echo ""
echo "Next steps:"
echo "1. Configure your .env file with environment variables"
echo "2. Update domain in /etc/nginx/sites-available/$NGINX_SITE"
echo "3. Set up SSL: sudo certbot --nginx -d your-domain.com"
echo "4. Check logs: journalctl -u $SERVICE_NAME -f"
echo ""
echo "Useful commands:"
echo "  Restart app: sudo systemctl restart $SERVICE_NAME"
echo "  View logs: sudo journalctl -u $SERVICE_NAME -f"
echo "  Reload Nginx: sudo systemctl reload nginx"
