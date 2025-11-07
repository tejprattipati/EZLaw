from flask import Flask, render_template, jsonify, request
import requests
import zipfile
import json
import io
import tempfile
import os
from google import genai

app = Flask(__name__)

# Configure Gemini API (google-genai client)
# Make sure GEMINI_API_KEY is set in your environment

genai_client = genai.Client(api_key="Key") 

@app.route('/')
def index():
    """Serve the main JSON viewer page"""
    return render_template('index.html')

@app.route('/chat')
def chat():
    """Serve the chat page with floating chatbot and inline search"""
    return render_template('chat.html')

@app.route('/results')
def results():
    """Serve the results page with user message and Gemini response"""
    user_message = request.args.get('user_message', '')
    gemini_response = request.args.get('gemini_response', '')
    return render_template('results.html', user_message=user_message, gemini_response=gemini_response)

@app.route('/laws')
def laws():
    """Serve the laws page with bill documents"""
    return render_template('laws.html')


@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """Handle chatbot messages using Gemini API"""
    try:
        if not genai_client:
            return jsonify({
                'success': False,
                'error': 'Gemini API not configured. Please set GEMINI_API_KEY environment variable.'
            }), 500
        
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        user_message = data['message']
        
        # Generate response using Gemini (google-genai client)
        result = genai_client.models.generate_content(
            model="gemini-2.5-pro",
            contents="You are a lookup machine that will only return the top 3 bill ids sorted in order of relevance with one being garunteed to be relevant and less progressive at number 3, we need these bill ids in the database related to the user input for" + 
            f"congress API bill lookup ONLY RETURN THE BILL IDS, CONGRESS NUMBER AND NOTHING ELSE in the form: hr.1234.118, then use a bar to seperate elements (laws), this is the user's input:" + user_message
        )
        
        # Store Gemini result for later use
        gemini_response = result.text

        parts = gemini_response.split("|")

# Make sure we only take the first three messages
        message1 = parts[0].strip() if len(parts) > 0 else None
        message2 = parts[1].strip() if len(parts) > 1 else None
        message3 = parts[2].strip() if len(parts) > 2 else None

        type1, number1, congress1 = message1.split(".")
        type2, number2, congress2 = message2.split(".")
        type3, number3, congress3 = message3.split(".")

        return jsonify({
            'success': True,
            'response': result.text
        })
        
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error processing message: {str(e)}'
        }), 500

@app.route('/api/legal-analysis', methods=['POST'])
def legal_analysis():
    """Provide detailed legal analysis using Gemini API"""
    try:
        if not genai_client:
            return jsonify({
                'success': False,
                'error': 'Gemini API not configured. Please set GEMINI_API_KEY environment variable.'
            }), 500
        
        data = request.get_json()
        if not data or 'user_message' not in data or 'bills' not in data:
            return jsonify({
                'success': False,
                'error': 'User message and bills are required'
            }), 400
        
        user_message = data['user_message']
        bills = data['bills']
        
        # Generate detailed legal analysis using Gemini
        result = genai_client.models.generate_content(
            model="gemini-2.5-pro",
            contents=f"""You are a legal expert providing detailed analysis. The user has asked: "{user_message}"

The relevant bills identified are: {bills}

Please provide a comprehensive legal analysis that includes:
1. How these bills relate to the user's situation
2. The legal implications and potential outcomes
3. What the user should know about these bills
4. Any relevant legal precedents or considerations
5. Practical next steps or recommendations

Write in a clear, professional tone that a layperson can understand. Focus on practical legal advice and implications."""
        )
        
        return jsonify({
            'success': True,
            'analysis': result.text
        })
        
    except Exception as e:
        print(f"Legal analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error generating legal analysis: {str(e)}'
        }), 500

@app.route('/api/law-details')
def law_details():
    """Fetch law details from Congress API"""
    try:
        bill_id = request.args.get('bill_id')
        if not bill_id:
            return jsonify({
                'success': False,
                'error': 'Bill ID is required'
            }), 400
        
        # Parse bill ID (e.g., "hr.3076.117" -> "hr", "3076", "117")
        parts = bill_id.split('.')
        if len(parts) != 3:
            return jsonify({
                'success': False,
                'error': 'Invalid bill ID format. Expected format: type.number.congress'
            }), 400
        
        bill_type, bill_number, congress = parts
        
        # Congress API endpoint
        api_key = "glfBcsEpbWcyXzpxqsheaptSuuhvFcdl2TKbdysA"
        api_url = f"https://api.congress.gov/v3/bill/{congress}/{bill_type.lower()}/{bill_number}?format=json&api_key={api_key}"
        
        print(f"Fetching law details from Congress API: {api_url}")
        
        # Make request to Congress API
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        
        # Parse the JSON response
        api_data = response.json()
        
        if 'bill' not in api_data:
            return jsonify({
                'success': False,
                'error': 'No bill data found in API response'
            }), 400
        
        bill_data = api_data['bill']
        
        # Fetch text versions if available
        text_content = ""
        text_versions_url = bill_data.get('textVersions', {}).get('url', '')
        
        if text_versions_url:
            try:
                # Fetch text versions
                text_response = requests.get(f"{text_versions_url}&api_key={api_key}", timeout=30)
                text_response.raise_for_status()
                text_data = text_response.json()
                
                # Get the latest text version
                if 'textVersions' in text_data and text_data['textVersions']:
                    latest_text = text_data['textVersions'][0]  # Get the first (latest) version
                    text_url = latest_text.get('url', '')
                    
                    if text_url:
                        # Fetch the actual text content
                        text_content_response = requests.get(f"{text_url}&api_key={api_key}", timeout=30)
                        text_content_response.raise_for_status()
                        text_content_data = text_content_response.json()
                        
                        # Extract text content
                        if 'text' in text_content_data:
                            text_content = text_content_data['text']
                        elif 'textVersions' in text_content_data and text_content_data['textVersions']:
                            text_content = text_content_data['textVersions'][0].get('text', '')
                            
            except Exception as e:
                print(f"Error fetching text content: {str(e)}")
                text_content = "Text content not available"
        
        # Extract relevant information
        law_info = {
            'title': bill_data.get('title', ''),
            'number': bill_data.get('number', ''),
            'type': bill_data.get('type', ''),
            'congress': bill_data.get('congress', ''),
            'introducedDate': bill_data.get('introducedDate', ''),
            'latestAction': bill_data.get('latestAction', {}),
            'policyArea': bill_data.get('policyArea', {}),
            'legislationUrl': bill_data.get('legislationUrl', ''),
            'sponsors': bill_data.get('sponsors', []),
            'subjects': bill_data.get('subjects', {}),
            'textVersions': bill_data.get('textVersions', {}),
            'summaries': bill_data.get('summaries', {}),
            'actions': bill_data.get('actions', {}),
            'committees': bill_data.get('committees', {}),
            'cosponsors': bill_data.get('cosponsors', {}),
            'laws': bill_data.get('laws', []),
            'textContent': text_content
        }
        
        return jsonify({
            'success': True,
            'law': law_info
        })
        
    except requests.RequestException as e:
        print(f"Congress API request error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to fetch data from Congress API: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error processing Congress API data: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=3003)
