39.106.173.81
调试URL https://libstr.dxsuite.cn/wxpayv3


vi /etc/nginx/conf.d/libstr.conf

cd /var/apps/wxpay-backend/
ps aux | grep python

pip install -r requirements.txt

python3 examples.py

## 后台运行，注意是用python >=3.4
nohup python3 examples.py &

