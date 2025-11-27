#!/bin/bash

# Ocean Viking Rescues - Simplified Deployment for Infomaniak Cloud Server
# This script is for use WITH Infomaniak's Port Redirection feature
# Configure port redirection in Infomaniak Manager: 80->8000 and 443->8000

set -e  # Exit on error

echo "=========================================="
echo "Ocean Viking - Infomaniak Simple Deploy"
echo "=========================================="

# Configuration
APP_DIR="/var/www/ocean-viking-rescues"
SERVICE_NAME="ocean-viking"

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
echo -e "${YELLOW}[1/7] Updating system packages...${NC}"
apt update && apt upgrade -y

# Step 2: Install dependencies (NO NGINX)
echo -e "${YELLOW}[2/7] Installing dependencies...${NC}"
apt install -y python3 python3-pip python3-venv curl

# Step 3: Create application directory
echo -e "${YELLOW}[3/7] Creating application directory...${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

# Step 4: Set up virtual environment
echo -e "${YELLOW}[4/7] Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Step 5: Install Python packages
echo -e "${YELLOW}[5/7] Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Step 6: Set permissions
echo -e "${YELLOW}[6/7] Setting permissions...${NC}"
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Step 7: Set up systemd service
echo -e "${YELLOW}[7/7] Setting up systemd service...${NC}"
cp ocean-viking.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# Check service status
echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
systemctl status $SERVICE_NAME --no-pager
echo ""
echo -e "${GREEN}Application is running on port 8000!${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: Configure Infomaniak Port Redirection${NC}"
echo "1. Go to Infomaniak Manager → Cloud Server → Network"
echo "2. Add Port Redirection:"
echo "   - External: 80 → Internal: 8000 (HTTP)"
echo "   - External: 443 → Internal: 8000 (HTTPS)"
echo "3. Configure SSL in Infomaniak Manager → SSL Certificates"
echo ""
echo "Next steps:"
echo "1. Configure your .env file: nano $APP_DIR/.env"
echo "2. Restart app: sudo systemctl restart $SERVICE_NAME"
echo "3. Set up Infomaniak port redirection (see above)"
echo ""
echo "Useful commands:"
echo "  Restart app: sudo systemctl restart $SERVICE_NAME"
echo "  View logs: sudo journalctl -u $SERVICE_NAME -f"
echo "  Check status: sudo systemctl status $SERVICE_NAME"
