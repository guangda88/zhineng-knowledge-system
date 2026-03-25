  #!/bin/bash
  # -*- coding: utf-8 -*-
  #
  #     : SafeLine, Node Exporter,

  set -e

  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  NC='\033[0m'

  if [ "$EUID" -ne 0 ]; then
      echo -e "${RED}       root         : sudo bash $0${NC}"
      exit 1
  fi

  echo "=========================================="
  echo "                "
  echo "=========================================="
  echo ""

  # 1.      Node Exporter (      )
  echo -e "${YELLOW}[1/3]${NC}      Node Exporter..."
  if [ -f /usr/local/bin/node_exporter ]; then
      echo "Node Exporter             "
  else
      useradd -rs /bin/false node_exporter || echo "              "
      wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz -
O /tmp/node_exporter.tar.gz
      tar xvfz /tmp/node_exporter.tar.gz -C /tmp/
      mv /tmp/node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/
      chown node_exporter:node_exporter /usr/local/bin/node_exporter

      cat <<'SERVICE' >/etc/systemd/system/node_exporter.service
  [Unit]
  Description=Node Exporter
  After=network.target

  [Service]
  Type=simple
  User=node_exporter
  ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100

  [Install]
  WantedBy=multi-user.target
  SERVICE

      systemctl daemon-reload
      systemctl enable node_exporter
      systemctl restart node_exporter
      echo -e "${GREEN}Node Exporter         ${NC}"
  fi

  # 2.      SafeLine
  echo -e "${YELLOW}[2/3]${NC}      SafeLine..."
  if docker ps | grep -q safeline-mgt; then
      echo "SafeLine             "
  else
      bash -c "$(curl -fsSLk https://waf-ce.chaitin.cn/release/latest/setup.sh)" || echo "SafeLine
(          )"
      echo -e "${GREEN}SafeLine         ${NC}"
  fi

  # 3.
  echo -e "${YELLOW}[3/3]${NC}         ..."
  apt update > /dev/null 2>&1
  apt install -y ufw fail2ban > /dev/null 2>&1

  ufw --force enable > /dev/null 2>&1
  ufw default deny incoming > /dev/null 2>&1
  ufw default allow outgoing > /dev/null 2>&1
  ufw allow ssh > /dev/null 2>&1
  ufw allow 9100/tcp > /dev/null 2>&1
  ufw allow 9443/tcp > /dev/null 2>&1
  ufw reload > /dev/null 2>&1

  sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
  sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
  systemctl restart sshd > /dev/null 2>&1

  systemctl enable fail2ban > /dev/null 2>&1
  systemctl start fail2ban > /dev/null 2>&1

  echo -e "${GREEN}            ${NC}"

  echo ""
  echo "=========================================="
  echo "          "
  echo "=========================================="
  echo ""
  echo "Node Exporter: http://$(hostname -I | awk '{print $1}'):9100"
  echo "SafeLine: https://$(hostname -I | awk '{print $1}'):9443"
  echo ""
