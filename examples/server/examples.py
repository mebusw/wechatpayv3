# -*- coding: utf-8 -*-
### 常见问题 https://github.com/mebusw/wechatpayv3/blob/master/docs/Q&A.md
### 调试URL https://libstr.dxsuite.cn/wxpayv3
import json
import logging
import os
from dotenv import load_dotenv
from random import sample
from string import ascii_letters, digits
import time
import uuid
import requests

from flask import Flask, jsonify, request

from wechatpayv3 import WeChatPay, WeChatPayType

load_dotenv()

# 微信支付商户号（直连模式）或服务商商户号（服务商模式，即sp_mchid)
MCHID = os.getenv('MCHID')

# 商户证书私钥
current_dir = os.path.dirname(__file__)
APICLIENT_KEY_FILE_PATH = os.getenv('APICLIENT_KEY_FILE_PATH')
private_key_file_path = os.path.join(current_dir, APICLIENT_KEY_FILE_PATH)
with open(private_key_file_path) as f:
    PRIVATE_KEY = f.read()

# 商户证书序列号
CERT_SERIAL_NO = os.getenv('CERT_SERIAL_NO')

# API v3密钥， https://pay.weixin.qq.com/wiki/doc/apiv3/wechatpay/wechatpay3_2.shtml
APIV3_KEY = os.getenv('APIV3_KEY')

# APPID，应用ID或服务商模式下的sp_appid
APPID = os.getenv('APPID')
APP_SECRET = os.getenv('APP_SECRET')

# 回调地址，也可以在调用接口的时候覆盖
DOMAIN_NAME = os.getenv('DOMAIN_NAME')
URL_PREFIX = os.getenv('URL_PREFIX')
NOTIFY_URL = DOMAIN_NAME + URL_PREFIX + '/notify'


# 微信支付平台证书缓存目录，减少证书下载调用次数，首次使用确保此目录为空目录.
# 初始调试时可不设置，调试通过后再设置，示例值:'./cert'
CERT_DIR = None

# 日志记录器，记录web请求和回调细节
logging.basicConfig(filename=os.path.join(os.getcwd(), 'demo.log'), level=logging.DEBUG, filemode='a', format='%(asctime)s - %(process)s - %(levelname)s: %(message)s')
LOGGER = logging.getLogger("demo")

# 接入模式:False=直连商户模式，True=服务商模式
PARTNER_MODE = False

# 代理设置，None或者{"https": "http://10.10.1.10:1080"}，详细格式参见https://requests.readthedocs.io/en/latest/user/advanced/#proxies
PROXY = None

# 请求超时时间配置
TIMEOUT = (10, 30) # 建立连接最大超时时间是10s，读取响应的最大超时时间是30s

# 初始化
wxpay = WeChatPay(
    wechatpay_type=WeChatPayType.NATIVE,
    mchid=MCHID,
    private_key=PRIVATE_KEY,
    cert_serial_no=CERT_SERIAL_NO,
    apiv3_key=APIV3_KEY,
    appid=APPID,
    notify_url=NOTIFY_URL,
    cert_dir=CERT_DIR,
    logger=LOGGER,
    partner_mode=PARTNER_MODE,
    proxy=PROXY,
    timeout=TIMEOUT
)

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({'code': 200, 'message': "It works, Flask!"})


@app.route(URL_PREFIX + '/')
def home():
    print(__name__)
    return jsonify({'code': 200, 'message': "It works, Hommi!"})


@app.route(URL_PREFIX + '/pay')
def pay():
    # 以native下单为例，下单成功后即可获取到'code_url'，将'code_url'转换为二维码，并用微信扫码即可进行支付测试。
    out_trade_no = ''.join(sample(ascii_letters + digits, 8))
    description = 'demo-description'
    amount = 1

    print('pay as NATIVE with out_trade_no: %s', out_trade_no)
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        pay_type=WeChatPayType.NATIVE
    )
    return jsonify({'code': code, 'message': message})


@app.route(URL_PREFIX + '/pay_jsapi')
def pay_jsapi():
    # 以jsapi下单为例，下单成功后，将prepay_id和其他必须的参数组合传递给JSSDK的wx.chooseWXPay接口唤起支付
    out_trade_no = ''.join(sample(ascii_letters + digits, 8))
    description = 'demo-description'
    amount = 1
    payer = {'openid': 'demo-openid'}
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        pay_type=WeChatPayType.JSAPI,
        payer=payer
    )
    result = json.loads(message)
    if code in range(200, 300):
        prepay_id = result.get('prepay_id')
        timestamp = str(int(time.time()))
        noncestr = str(uuid.uuid4()).replace('-', '')
        package = 'prepay_id=' + prepay_id
        sign = wxpay.sign([APPID, timestamp, noncestr, package])
        signtype = 'RSA'
        return jsonify({'code': 0, 'result': {
            'appId': APPID,
            'timeStamp': timestamp,
            'nonceStr': noncestr,
            'package': 'prepay_id=%s' % prepay_id,
            'signType': signtype,
            'paySign': sign
        }})
    else:
        return jsonify({'code': -1, 'result': {'reason': result.get('code')}})


@app.route(URL_PREFIX + '/pay_h5')
def pay_h5():
    # 以h5下单为例，下单成功后，将获取的的h5_url传递给前端跳转唤起支付。
    out_trade_no = ''.join(sample(ascii_letters + digits, 8))
    description = 'demo-description'
    amount = 1
    scene_info = {'payer_client_ip': '1.2.3.4', 'h5_info': {'type': 'Wap'}}
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        pay_type=WeChatPayType.H5,
        scene_info=scene_info
    )
    return jsonify({'code': code, 'message': message})


@app.route(URL_PREFIX + '/pay_miniprog', methods=['POST'])
def pay_miniprog():
    print('receiving... /pay_miniprog')
    openid = request.json.get('openid')
    description = request.json.get('description')

    # 以小程序下单为例，下单成功后，将prepay_id和其他必须的参数组合传递给小程序的wx.requestPayment接口唤起支付
    out_trade_no = ''.join(sample(ascii_letters + digits, 8))
    amount = 1   ### 总金额，单位为分

    print('/pay_miniprog:  ', openid, description, out_trade_no, amount)

    print('pay as MINIPROG with out_trade_no: %s', out_trade_no)
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        pay_type=WeChatPayType.MINIPROG,
        payer={'openid': openid}
    )
    result = json.loads(message)
    if code in range(200, 300):
        prepay_id = result.get('prepay_id')
        timestamp = str(int(time.time()))
        noncestr = str(uuid.uuid4()).replace('-', '')
        package = 'prepay_id=' + prepay_id
        sign = wxpay.sign(data=[APPID, timestamp, noncestr, package])
        signtype = 'RSA'
        return jsonify({'code': 0, 'result': {
            'appId': APPID,
            'timeStamp': timestamp,
            'nonceStr': noncestr,
            'package': 'prepay_id=%s' % prepay_id,
            'signType': signtype,
            'paySign': sign
        }})
    else:
        return jsonify({'code': -1, 'result': {'reason': result.get('code')}})


@app.route(URL_PREFIX + '/pay_app')
def pay_app():
    # 以app下单为例，下单成功后，将prepay_id和其他必须的参数组合传递给IOS或ANDROID SDK接口唤起支付
    out_trade_no = ''.join(sample(ascii_letters + digits, 8))
    description = 'demo-description'
    amount = 1
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        pay_type=WeChatPayType.APP
    )
    result = json.loads(message)
    if code in range(200, 300):
        prepay_id = result.get('prepay_id')
        timestamp = str(int(time.time()))
        noncestr = str(uuid.uuid4()).replace('-', '')
        package = 'Sign=WXPay'
        sign = wxpay.sign(data=[APPID, timestamp, noncestr, prepay_id])
        return jsonify({'code': 0, 'result': {
            'appid': APPID,
            'partnerid': MCHID,
            'prepayid': prepay_id,
            'package': package,
            'nonceStr': noncestr,
            'timestamp': timestamp,
            'sign': sign
        }})
    else:
        return jsonify({'code': -1, 'result': {'reason': result.get('code')}})

@app.route(URL_PREFIX + '/pay_codepay')
def pay_codeapp():
    # 以付款码支付为例，终端条码枪扫描用户付款码将解码后的auth_code放入payer传递给微信支付服务器扣款。
    out_trade_no = ''.join(sample(ascii_letters + digits, 8))
    description = 'demo-description'
    amount = 1
    payer = {'auth_code': '130061098828009406'}
    scene_info={'store_info' : {'id' : '0001'}}
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        payer=payer,
        scene_info=scene_info,
        pay_type=WeChatPayType.CODEPAY
    )
    result = json.loads(message)
    if code in range(200, 300):
        trade_state = result.get('trade_state')
        trade_state_desc = result.get('trade_state_desc')
        if trade_state == 'SUCCESS':
            # 扣款成功，提示终端做后续处理
            return jsonify({'code': 0, 'result': {'reason': trade_state_desc}})
        else:
            # 扣款失败，提示终端做后续处理
            return jsonify({'code': -1, 'result': {'reason': trade_state_desc}})
    else:
        return jsonify({'code': -1, 'result': {'reason': result.get('code')}})

@app.route(URL_PREFIX + '/notify', methods=['POST'])
def notify():
    print('received nofify')
    ###由于 django 框架特殊性，会将 headers 做一定的预处理，可以参考以下方式调用。
    # headers = {
    # 'Wechatpay-Signature': request.META.get('HTTP_WECHATPAY_SIGNATURE'),
    # 'Wechatpay-Timestamp': request.META.get('HTTP_WECHATPAY_TIMESTAMP'),
    # 'Wechatpay-Nonce': request.META.get('HTTP_WECHATPAY_NONCE'),
    # 'Wechatpay-Serial': request.META.get('HTTP_WECHATPAY_SERIAL')
    # }
    # result = wxpay.callback(headers=headers, body=request.body)
    ###

    result = wxpay.callback(request.headers, request.data)
    if result and result.get('event_type') == 'TRANSACTION.SUCCESS':
        resp = result.get('resource')
        appid = resp.get('appid')
        mchid = resp.get('mchid')
        out_trade_no = resp.get('out_trade_no')
        transaction_id = resp.get('transaction_id')
        trade_type = resp.get('trade_type')
        trade_state = resp.get('trade_state')
        trade_state_desc = resp.get('trade_state_desc')
        bank_type = resp.get('bank_type')
        attach = resp.get('attach')
        success_time = resp.get('success_time')
        payer = resp.get('payer')
        amount = resp.get('amount').get('total')
        # TODO: 根据返回参数进行必要的业务处理，处理完后返回200或204
        print('notified out_trade_no: ', out_trade_no)
        ## 实际开发中处理微信支付通知消息时有两个问题需要注意。一是可能会重复收到同一个通知消息，需要在代码中进行判断处理。另一个是处理消息的时间如果过长，建议考虑异步处理，先缓存消息，避免微信支付服务器端认为超时，如果持续超时，微信支付服务器端可能会认为回调消息接口不可用。
        return jsonify({'code': 'SUCCESS', 'message': '成功'})
    else:
        return jsonify({'code': 'FAILED', 'message': '失败'}), 500

@app.route(URL_PREFIX + '/wxLogin', methods=['POST'])
def wxLogin():
    code = request.json.get('code')
    try:
        openid, session_key = get_openid_and_session_key(code)
        return jsonify({'openid': openid, 'session_key': session_key})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def get_openid_and_session_key(code):
    url = f'https://api.weixin.qq.com/sns/jscode2session?appid={APPID}&secret={APP_SECRET}&js_code={code}&grant_type=authorization_code'

    response = requests.get(url)
    data = response.json()

    if 'openid' in data:
        openid = data['openid']
        session_key = data['session_key']
        return openid, session_key
    else:
        raise Exception(f"Error fetching openid: {data.get('errmsg')}")


if __name__ == '__main__':
    app.run(debug=True)