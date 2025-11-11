from flask import Flask, request, jsonify
import subprocess
import json
import time
import threading
import concurrent.futures
from datetime import datetime

app = Flask(__name__)

# Import your original rz.py functions
from rz import check_url_and_capture

class ParallelCardChecker:
    def __init__(self):
        self.results = {}
    
    def run_php_check(self, lista, amount, site):
        """Execute autorazorpay.php in thread"""
        try:
            start_time = time.time()
            cmd = [
                'php', 'autorazorpay.php', 
                f'--lista={lista}',
                f'--amount={amount}', 
                f'--site={site}'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            processing_time = round(time.time() - start_time, 3)
            
            php_data = json.loads(result.stdout) if result.stdout else {}
            
            self.results['php'] = {
                'raw': php_data,
                'processing_time': processing_time,
                'success': php_data.get('success', False),
                'status': 'completed'
            }
        except Exception as e:
            self.results['php'] = {
                'error': str(e),
                'success': False,
                'status': 'failed',
                'processing_time': 0
            }
    
    def run_py_check(self, site, lista):
        """Execute rz.py check in thread"""
        try:
            start_time = time.time()
            py_result = check_url_and_capture(site)
            processing_time = round(time.time() - start_time, 3)
            
            self.results['py'] = {
                'raw': py_result,
                'processing_time': processing_time,
                'success': py_result.get('3ds', False),
                'status': 'completed'
            }
        except Exception as e:
            self.results['py'] = {
                'error': str(e),
                'success': False, 
                'status': 'failed',
                'processing_time': 0
            }

def parse_php_response(php_data, lista):
    """Parse PHP response to standard format"""
    parts = lista.split('|')
    card_bin = parts[0][:6] if len(parts[0]) >= 6 else parts[0]
    
    if php_data.get('success'):
        return {
            "method": "php",
            "success": True,
            "payment_status": "captured",
            "amount_captured": True,
            "gateway_response": "CAPTURED",
            "amount": php_data.get('amount', '100'),
            "currency": "INR",
            "card_bin": card_bin,
            "card_type": php_data.get('card_type', 'Visa'),
            "card_scheme": php_data.get('card_scheme', 'VISA'),
            "card_category": php_data.get('card_category', 'CREDIT'),
            "merchant_site": php_data.get('merchant_site', ''),
            "site_type": "custom_razorpay_me",
            "key_id_detected": True,
            "transaction_id": f"txn_php_{int(time.time())}",
            "device_id": php_data.get('device_id', ''),
            "timestamp": int(time.time()),
            "message": "✅ PHP: Payment Captured",
            "bank_message": "PHP: Transaction completed",
            "processing_time": php_data.get('processing_time', 1.185),
            "risk_level": "low",
            "avs_result": "U",
            "cvv_result": "Y"
        }
    else:
        return {
            "method": "php", 
            "success": False,
            "payment_status": "declined",
            "amount_captured": False,
            "gateway_response": "DECLINED",
            "amount": php_data.get('amount', '100'),
            "currency": "INR",
            "card_bin": card_bin,
            "card_type": php_data.get('card_type', ''),
            "card_scheme": php_data.get('card_scheme', ''),
            "card_category": php_data.get('card_category', ''),
            "merchant_site": php_data.get('merchant_site', ''),
            "site_type": "custom_razorpay_me",
            "key_id_detected": php_data.get('key_id_detected', False),
            "transaction_id": f"txn_php_{int(time.time())}_declined",
            "device_id": php_data.get('device_id', ''),
            "timestamp": int(time.time()),
            "message": "❌ PHP: Payment Declined",
            "bank_message": php_data.get('message', 'PHP: Bank declined'),
            "processing_time": php_data.get('processing_time', 1.185),
            "risk_level": "high",
            "avs_result": "N",
            "cvv_result": "N"
        }

def parse_py_response(py_data, lista):
    """Parse Python response to standard format"""
    parts = lista.split('|')
    card_bin = parts[0][:6] if len(parts[0]) >= 6 else parts[0]
    
    if py_data.get('3ds'):
        return {
            "method": "python",
            "success": True,
            "payment_status": "captured",
            "amount_captured": True,
            "gateway_response": "CAPTURED",
            "amount": "100",
            "currency": "INR",
            "card_bin": card_bin,
            "card_type": "Visa",
            "card_scheme": "VISA",
            "card_category": "CREDIT",
            "merchant_site": "razorpay_check",
            "site_type": "rz_py_checker",
            "key_id_detected": True,
            "transaction_id": f"txn_py_{int(time.time())}",
            "device_id": f"rzpy_{int(time.time())}",
            "timestamp": int(time.time()),
            "message": "✅ Python: 3DS Captured",
            "bank_message": py_data.get('message', 'Python: 3DS Successful'),
            "processing_time": py_data.get('processing_time', 1.185),
            "risk_level": "low",
            "avs_result": "U",
            "cvv_result": "Y"
        }
    else:
        return {
            "method": "python",
            "success": False,
            "payment_status": "declined",
            "amount_captured": False,
            "gateway_response": "DECLINED",
            "amount": "100",
            "currency": "INR",
            "card_bin": card_bin,
            "card_type": "Visa",
            "card_scheme": "VISA",
            "card_category": "CREDIT",
            "merchant_site": "razorpay_check",
            "site_type": "rz_py_checker",
            "key_id_detected": True,
            "transaction_id": f"txn_py_{int(time.time())}_declined",
            "device_id": f"rzpy_{int(time.time())}",
            "timestamp": int(time.time()),
            "message": "❌ Python: 3DS Failed",
            "bank_message": py_data.get('message', 'Python: 3DS Failed'),
            "processing_time": py_data.get('processing_time', 1.185),
            "risk_level": "high",
            "avs_result": "N",
            "cvv_result": "N"
        }

@app.route('/api/check/parallel', methods=['GET'])
def parallel_check():
    """Execute both PHP and Python checks simultaneously"""
    start_time = time.time()
    
    # Get parameters
    lista = request.args.get('lista')  # CC|MM|YY|CVV
    amount = request.args.get('amount', '100')
    site = request.args.get('site', '')
    
    if not lista or not site:
        return jsonify({
            "success": False,
            "error": "Missing parameters: lista and site required"
        }), 400
    
    checker = ParallelCardChecker()
    
    # Run both checks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        php_future = executor.submit(checker.run_php_check, lista, amount, site)
        py_future = executor.submit(checker.run_py_check, site, lista)
        
        # Wait for both to complete
        concurrent.futures.wait([php_future, py_future], timeout=35)
    
    # Parse results
    php_result = parse_php_response(checker.results.get('php', {}).get('raw', {}), lista)
    py_result = parse_py_response(checker.results.get('py', {}).get('raw', {}), lista)
    
    # Determine overall status
    php_success = checker.results.get('php', {}).get('success', False)
    py_success = checker.results.get('py', {}).get('success', False)
    
    overall_success = php_success or py_success  # Card is valid if either method works
    
    # Build combined response
    combined_response = {
        "success": overall_success,
        "payment_status": "captured" if overall_success else "declined",
        "amount_captured": overall_success,
        "gateway_response": "CAPTURED" if overall_success else "DECLINED",
        "combined_confidence": "high" if php_success and py_success else "medium" if php_success or py_success else "low",
        "methods_tested": 2,
        "methods_successful": sum([php_success, py_success]),
        "total_processing_time": round(time.time() - start_time, 3),
        "timestamp": int(time.time()),
        "card_bin": lista.split('|')[0][:6],
        "amount": amount,
        "currency": "INR",
        "individual_results": {
            "php": {
                "success": php_success,
                "processing_time": checker.results.get('php', {}).get('processing_time', 0),
                "message": php_result.get('message', ''),
                "bank_message": php_result.get('bank_message', ''),
                "status": checker.results.get('php', {}).get('status', 'unknown')
            },
            "python": {
                "success": py_success,
                "processing_time": checker.results.get('py', {}).get('processing_time', 0),
                "message": py_result.get('message', ''),
                "bank_message": py_result.get('bank_message', ''),
                "status": checker.results.get('py', {}).get('status', 'unknown')
            }
        },
        "recommendation": "APPROVE" if overall_success else "DECLINE",
        "risk_analysis": {
            "php_risk": "low" if php_success else "high",
            "python_risk": "low" if py_success else "high", 
            "overall_risk": "low" if overall_success else "high"
        }
    }
    
    # Add detailed results if available
    if php_success:
        combined_response.update({
            "transaction_id": php_result.get('transaction_id'),
            "device_id": php_result.get('device_id'),
            "merchant_site": php_result.get('merchant_site'),
            "card_type": php_result.get('card_type'),
            "card_scheme": php_result.get('card_scheme')
        })
    elif py_success:
        combined_response.update({
            "transaction_id": py_result.get('transaction_id'),
            "device_id": py_result.get('device_id'),
            "merchant_site": py_result.get('merchant_site'),
            "card_type": py_result.get('card_type'),
            "card_scheme": py_result.get('card_scheme')
        })
    
    return jsonify(combined_response)

@app.route('/api/check/php', methods=['GET'])
def php_only_check():
    """PHP-only check endpoint"""
    return check_card_single(method='php')

@app.route('/api/check/python', methods=['GET'])  
def python_only_check():
    """Python-only check endpoint"""
    return check_card_single(method='py')

def check_card_single(method):
    """Single method check"""
    start_time = time.time()
    
    lista = request.args.get('lista')
    amount = request.args.get('amount', '100')
    site = request.args.get('site', '')
    
    if not lista:
        return jsonify({"success": False, "error": "Missing parameter: lista"}), 400
    
    try:
        if method == 'php':
            if not site:
                return jsonify({"success": False, "error": "Site parameter required for PHP method"}), 400
            cmd = ['php', 'autorazorpay.php', f'--lista={lista}', f'--amount={amount}', f'--site={site}']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout) if result.stdout else {}
            response = parse_php_response(data, lista)
        else:
            if not site:
                return jsonify({"success": False, "error": "Site parameter required for Python method"}), 400
            py_result = check_url_and_capture(site)
            response = parse_py_response(py_result, lista)
        
        response["processing_time"] = round(time.time() - start_time, 3)
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"{method.upper()} execution failed: {str(e)}",
            "processing_time": round(time.time() - start_time, 3)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "Parallel Card Checker API",
        "timestamp": int(time.time()),
        "capabilities": ["php_check", "python_check", "parallel_check"],
        "threading": "enabled"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
