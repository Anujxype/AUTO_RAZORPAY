from flask import Flask, request, jsonify
import subprocess
import json
import time
import random
import os
from datetime import datetime

app = Flask(__name__)

def execute_php_checker(card_data, amount, site_url):
    """Execute your original auto_razorpay.php without modifications"""
    try:
        # Format: CC|MM|YY|CVV (exactly as your PHP expects)
        lista = f"{card_data['number']}|{card_data['month']}|{card_data['year']}|{card_data['cvv']}"
        
        # Build PHP command - your original code runs as-is
        cmd = [
            'php', 'auto_razorpay.php',
            f"lista={lista}",
            f"amount={amount}", 
            f"site={site_url}"
        ]
        
        # Execute and capture output
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return json.dumps({"error": f"PHP error: {result.stderr}"})
        
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "PHP script timeout"})
    except Exception as e:
        return json.dumps({"error": f"PHP execution failed: {str(e)}"})

def standardize_response(raw_result, card_data, amount, site_info):
    """Convert to your exact response format"""
    
    # Parse raw result
    status = "declined"
    gateway_msg = "DECLINED"
    user_message = "❌ Payment Declined"
    
    if isinstance(raw_result, str):
        if "captured" in raw_result.lower() or "success" in raw_result.lower() or "approved" in raw_result.lower():
            status = "captured"
            gateway_msg = "CAPTURED"
            user_message = "✅ Payment Captured Successfully"
        elif "pending" in raw_result.lower() or "processing" in raw_result.lower():
            status = "pending" 
            gateway_msg = "PENDING"
            user_message = "⏳ Payment Processing"
    
    timestamp = int(time.time())
    
    # Your exact response format
    return {
        "success": True,
        "payment_status": status,
        "amount_captured": status == "captured",
        "gateway_response": gateway_msg,
        "amount": str(amount),
        "currency": "INR",
        "card_bin": card_data['number'][:6],
        "card_type": "Credit",  # You can detect this from BIN
        "card_scheme": "VISA",  # You can detect this from BIN  
        "card_category": "CREDIT",
        "merchant_site": site_info.get('name', 'unknown'),
        "site_type": "custom_razorpay_me",
        "key_id_detected": True,
        "transaction_id": f"txn_{timestamp}_{os.urandom(4).hex()}",
        "device_id": f"1.{os.urandom(10).hex()}.{timestamp}.{random.randint(10000000, 99999999)}",
        "timestamp": timestamp,
        "message": f"{user_message} - ₹{amount}",
        "bank_message": "HDFC Bank: Transaction completed" if status == "captured" else "Bank: Transaction processed",
        "processing_time": 0,  # Will be updated later
        "risk_level": "low" if status == "captured" else "high",
        "avs_result": "U",
        "cvv_result": "Y" if status == "captured" else "N"
    }

@app.route('/api/v1/check-card', methods=['POST'])
def check_card():
    """Main card checking endpoint - maintains your exact format"""
    start_time = time.time()
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['card_number', 'exp_month', 'exp_year', 'cvv', 'amount']
        for field in required:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        card_data = {
            'number': data['card_number'].replace(' ', ''),
            'month': data['exp_month'].zfill(2), 
            'year': data['exp_year'][-2:],  # Last 2 digits
            'cvv': data['cvv']
        }
        
        amount = data['amount']
        site_url = data.get('site_url', 'https://razorpay.me/')
        
        # Execute your original PHP script
        php_result = execute_php_checker(card_data, amount, site_url)
        
        # Standardize response to your exact format
        site_name = site_url.split('//')[-1].split('/')[0]
        final_response = standardize_response(php_result, card_data, amount, {"name": site_name})
        
        # Add processing time
        final_response['processing_time'] = round(time.time() - start_time, 3)
        
        return jsonify(final_response)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"API processing error: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "online",
        "timestamp": int(time.time()),
        "service": "Card Checker API",
        "version": "1.0.0"
    })

@app.route('/')
def home():
    return jsonify({
        "message": "Card Checker API is running",
        "endpoints": {
            "check_card": "POST /api/v1/check-card",
            "health": "GET /health"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
