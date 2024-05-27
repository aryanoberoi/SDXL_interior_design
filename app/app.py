
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import base64
import websocket 
import uuid
import json
import urllib.request
import urllib.parse
import numpy as np
from PIL import Image
import os
from flask_mysqldb import MySQL
import MySQLdb.cursors
import io
import csv
from io import BytesIO
import cloudinary
import cloudinary.uploader
import cloudinary.api
import re
from datetime import datetime
import random
cloudinary.config( 
  cloud_name = "dn3nt85k0", 
  api_key = "323136335994961", 
  api_secret = "e7LcQp3goyrZXJO-SaW48Zgevl0" 
)
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

app = Flask(__name__)
CORS(app)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'aidea'
app.config['MYSQL_DB'] = 'root'

# Intialize MySQL
mysql = MySQL(app)

app.secret_key = ' key'
def save_login_details(username, login_time):
    # Define the CSV file path
    csv_file_path = 'output/login_history.csv'

    # Check if the file exists, if not, create with headers
    file_exists = os.path.isfile(csv_file_path)

    # Open the file in append mode ('a')
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created
        if not file_exists:
            writer.writerow(['Username', 'Login Time'])

        # Write the data row
        writer.writerow([username, login_time])
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM acc WHERE username = %s AND password = %s', (username, password,))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['username'] = account['username']
            session['time']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_time=str(session['time'])
            save_login_details(username, current_time)
            return redirect(url_for('home'))
        else:
            msg = 'Incorrect username/password!'
    return render_template('login.html', msg=msg)

@app.route('/registerinternal', methods=['GET', 'POST'])
def register():
    # Output message if something goes wrong...
    msg = ''
    # Check if "username", "password" and "email" POST requests exist (user submitted form)
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        # Create variables for easy access
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Check if account exists using MySQL
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM acc WHERE username = %s', (username,))
        account = cursor.fetchone()
        # If account exists show error and validation checks
        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers!'
        elif not username or not password or not email:
            msg = 'Please fill out the form!'
        else:
            # Account doesnt exists and the form data is valid, now insert new account into accounts table
            cursor.execute('INSERT INTO acc VALUES (%s, %s, %s, NULL)', (username, email, password))
            mysql.connection.commit()
            msg = 'You have successfully registered!'
    elif request.method == 'POST':
        # Form is empty... (no POST data)
        msg = 'Please fill out the form!'
    # Show registration form with message (if any)
    return render_template('register.html', msg=msg)
@app.route('/login/logout')
def logout():
    # Remove session data, this will log the user out
    session.pop('loggedin', None)
    session.pop('username', None)
    # Redirect to login page
    return redirect(url_for('login'))

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()
def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())
def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
    output_images[node_id] = images_output

    return output_images


def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())
def getimg(fil):
        with open(fil, "r", encoding="utf-8") as f:
            workflow_jsondata = f.read()
            jsonwf = json.loads(workflow_jsondata)
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            images = get_images(ws, jsonwf)

        processed_image_base64 = None
        for node_id in images:
            if images[node_id]:  # Check if the list of images for this node is not empty
                image_data = images[node_id][0]  # Get the first image
                image = Image.open(io.BytesIO(image_data))
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")  # You can change the format if needed
                processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                return processed_image_base64
def getimgprompt(fil,prompt1,prompt2,prompt3):
        with open(fil, "r", encoding="utf-8") as f:
            workflow_jsondata = f.read()
            jsonwf = json.loads(workflow_jsondata)
            jsonwf["84"]["inputs"]["text"]=prompt1
            jsonwf["85"]["inputs"]["text"]=prompt2
            jsonwf["86"]["inputs"]["text"]=prompt3
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            images = get_images(ws, jsonwf)

        processed_image_base64 = None
        for node_id in images:
            if images[node_id]:  # Check if the list of images for this node is not empty
                image_data = images[node_id][0]  # Get the first image
                image = Image.open(io.BytesIO(image_data))
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")  # You can change the format if needed
                processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                return processed_image_base64
            
def getimgproduct(fil,prompt1,prompt2,prompt3):
        with open(fil, "r", encoding="utf-8") as f:
            workflow_jsondata = f.read()
            jsonwf = json.loads(workflow_jsondata)
            jsonwf["47"]["inputs"]["text"]=prompt1
            jsonwf["60"]["inputs"]["show_text"]=prompt2
            jsonwf["91"]["inputs"]["text"]=prompt3
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            images = get_images(ws, jsonwf)

        processed_image_base64 = None
        for node_id in images:
            if images[node_id]:  # Check if the list of images for this node is not empty
                image_data = images[node_id][0]  # Get the first image
                image = Image.open(io.BytesIO(image_data))
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")  # You can change the format if needed
                processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                return processed_image_base64
            

def getimgproduct2(fil,prompt1,prompt2):
        with open(fil, "r", encoding="utf-8") as f:
            workflow_jsondata = f.read()
            jsonwf = json.loads(workflow_jsondata)
            jsonwf["91"]["inputs"]["Text"]=prompt1
            jsonwf["83"]["inputs"]["Text"]=prompt2
            jsonwf["41"]["inputs"]["seed"]=random.randint(0, 100000)
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            images = get_images(ws, jsonwf)

        processed_image_base64 = None
        for node_id in images:
            if images[node_id]:  # Check if the list of images for this node is not empty
                image_data = images[node_id][0]  # Get the first image
                image = Image.open(io.BytesIO(image_data))
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")  # You can change the format if needed
                processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                return processed_image_base64
def getimgpromptSINGLE(fil,prompt1):
        with open(fil, "r", encoding="utf-8") as f:
            workflow_jsondata = f.read()
            jsonwf = json.loads(workflow_jsondata)
            jsonwf["243"]["inputs"]["prompt"]=prompt1
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            images = get_images(ws, jsonwf)

        processed_image_base64 = None
        for node_id in images:
            if images[node_id]:  # Check if the list of images for this node is not empty
                image_data = images[node_id][0]  # Get the first image
                image = Image.open(io.BytesIO(image_data))
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")  # You can change the format if needed
                processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                return processed_image_base64
@app.route('/interiorb2b')
def b2b():
    if 'loggedin' in session:
        return render_template('b2binterior.html')
    return redirect(url_for('home'))

@app.route('/product2')
def pr2():
    if 'loggedin' in session:
        return render_template('product2.html')
    return redirect(url_for('home'))
@app.route('/newinterior')
def newint():
    if 'loggedin' in session:
        return render_template('newinterior.html')
    return redirect(url_for('home'))

@app.route('/newonlyprompts')
def newintprompt():
    if 'loggedin' in session:
        return render_template('onlyprompts.html')
    return redirect(url_for('home'))
@app.route('/product1')
def sirproduct():
    if 'loggedin' in session:
        return render_template('product1.html')
    return redirect(url_for('home'))
@app.route('/')
def home():
    # Check if user is loggedin
    if 'loggedin' in session:
        # User is loggedin show them the home page
        return render_template('home.html')
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))
@app.route('/interiorb2c')
def b2c():
    if 'loggedin' in session:
        return render_template('b2cinterior.html')
    return redirect(url_for('home'))
@app.route('/feedbackb2c', methods=['POST'])
def feedback():
    feedback = request.form['feedback']
    room_type = request.form['room']
    style = request.form['style']
    add = request.form.get('additional')
    input_image = request.files.get('input_image')
    output_image_data = request.form.get('output_image')  # This will be a Base64 encoded string
    username=session['username']
    gentime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Define the CSV file path
    csv_file_path = 'C:/Users/Admin/Desktop/app/output/feedbackb2c.csv'

    # Check if the file exists, if not, create with headers
    file_exists = os.path.isfile(csv_file_path)

    # Open the file in append mode ('a')
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created
        if not file_exists:
            writer.writerow(['username', 'generation time', 'Feedback', 'Room Type', 'Style', 'additional arguments','Image Input URL', 'Image Output URL'])

        # Save the input image to a directory, upload to Cloudinary and get the URL
        input_image_url = ""
        if input_image:
            input_image_path = os.path.join('C:/Users/Admin/Desktop/app/output', input_image.filename)
            input_image.save(input_image_path)
            uploaded_response = cloudinary.uploader.upload(input_image_path)
            input_image_url = uploaded_response['url']

        # Process the output image, save to Cloudinary and get the URL
        output_image_url = ""
        if output_image_data:
            # Check if the Base64 data contains the header
            if ',' in output_image_data:
                output_image_data = output_image_data.split(",")[1]
            # Decode the Base64 string to an image
            image_data = base64.b64decode(output_image_data)
            image = Image.open(BytesIO(image_data))
            output_image_path = 'temp_output_image.png'  # Temp path
            image.save(output_image_path)
            uploaded_response = cloudinary.uploader.upload(output_image_path)
            output_image_url = uploaded_response['url']  # Clean up the temp file

        # Write the data row
        writer.writerow([username,gentime,feedback, room_type, style, add, input_image_url, output_image_url])

    return jsonify({"message": "Feedback received successfully"}), 200

@app.route('/feedbackb2b', methods=['POST'])
def feedbackb2b():
    feedback = request.form['feedback']
    room_type = request.form['room']
    style = request.form['style']
    input_image = request.files.get('input_image')
    output_image_data = request.form.get('output_image')  # This will be a Base64 encoded string
    username=session['username']
    gentime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Define the CSV file path
    csv_file_path = 'C:/Users/Admin/Desktop/app/output/feedbackLoracontrolnet.csv'

    # Check if the file exists, if not, create with headers
    file_exists = os.path.isfile(csv_file_path)

    # Open the file in append mode ('a')
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created
        if not file_exists:
            writer.writerow(['username', 'generation time', 'Feedback', 'Room Type', 'Style', 'Image Input URL', 'Image Output URL'])

        # Save the input image to a directory, upload to Cloudinary and get the URL
        input_image_url = ""
        if input_image:
            input_image_path = os.path.join('C:/Users/Admin/Desktop/app/output', input_image.filename)
            input_image.save(input_image_path)
            uploaded_response = cloudinary.uploader.upload(input_image_path)
            input_image_url = uploaded_response['url']

        # Process the output image, save to Cloudinary and get the URL
        output_image_url = ""
        if output_image_data:
            # Check if the Base64 data contains the header
            if ',' in output_image_data:
                output_image_data = output_image_data.split(",")[1]
            # Decode the Base64 string to an image
            image_data = base64.b64decode(output_image_data)
            image = Image.open(BytesIO(image_data))
            output_image_path = 'temp_output_image.png'  # Temp path
            image.save(output_image_path)
            uploaded_response = cloudinary.uploader.upload(output_image_path)
            output_image_url = uploaded_response['url'] 

        # Write the data row
        writer.writerow([username,gentime,feedback, room_type, style, input_image_url, output_image_url])

    return jsonify({"message": "Feedback received successfully"}), 200

@app.route('/feedbacknewinterior', methods=['POST'])
def interior3():
    feedback = request.form['feedback']
    input_image = request.files.get('input_image')
    add = request.form['room']
    output_image_data = request.form.get('output_image')  # This will be a Base64 encoded string
    username=session['username']
    gentime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # This will be a Base64 encoded string

    # Define the CSV file path
    csv_file_path = 'C:/Users/Admin/Desktop/app/output/feedbackinterior3.csv'

    # Check if the file exists, if not, create with headers
    file_exists = os.path.isfile(csv_file_path)

    # Open the file in append mode ('a')
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created
        if not file_exists:
            writer.writerow(['username','time','input','feedback', 'Image Input URL', 'Image Output URL'])

        # Save the input image to a directory, upload to Cloudinary and get the URL
        input_image_url = ""
        if input_image:
            input_image_path = os.path.join('C:/Users/Admin/Desktop/app/output', input_image.filename)
            input_image.save(input_image_path)
            uploaded_response = cloudinary.uploader.upload(input_image_path)
            input_image_url = uploaded_response['url']

        # Process the output image, save to Cloudinary and get the URL
        output_image_url = ""
        if output_image_data:
            # Check if the Base64 data contains the header
            if ',' in output_image_data:
                output_image_data = output_image_data.split(",")[1]
            # Decode the Base64 string to an image
            image_data = base64.b64decode(output_image_data)
            image = Image.open(BytesIO(image_data))
            output_image_path = 'temp_output_image.png'  # Temp path
            image.save(output_image_path)
            uploaded_response = cloudinary.uploader.upload(output_image_path)
            output_image_url = uploaded_response['url']  # Clean up the temp file

        # Write the data row
        writer.writerow([username,gentime,add,feedback, input_image_url, output_image_url,])

    return jsonify({"message": "Feedback received successfully"}), 200
@app.route('/getb2b', methods=['POST'])
def process_image():
    image_path = "D:\What an AIdea!\ComfyUI_windows_portable\ComfyUI\input\example.png"
    
    room = request.form['room']
    print(room)
    style = request.form['style']
    print(style)
    image_file = request.files['image']
    
    image_file.save(image_path)
    if room=='pujaroom' and style=='modern':
        pro=getimg("modernpujaapi.json")
    if room=='pujaroom' and style=='neoclassical':
        pro=getimg("neopuja.json")
    if room=='pujaroom' and style=='Cyberpunk':
        pro=getimg("cyberpuja.json")
    elif room=='living-room' and style=='modern':
        pro=getimg("modernlivingapi.json")
    elif room=='bedroom' and style=='modern':
        pro=getimg("modernbedapi.json")
    elif room=='kitchen' and style=='modern':
        pro=getimg("modernkitchenapi.json")
    elif room=='living-room' and style=='neoclassical':
        pro=getimg("neolivingapi.json")
    elif room=='bedroom' and style=='neoclassical':
        pro=getimg("neobedapi.json")
    elif room=='kitchen' and style=='neoclassical':
        pro=getimg("neokitchenapi.json")
    elif room=='living-room' and style=='Cyberpunk':
        pro=getimg("cyberlivapi.json")
    elif room=='bedroom' and style=='Cyberpunk':
        pro=getimg("cyberbedapi.json")
    elif room=='kitchen' and style=='Cyberpunk':
        pro=getimg("cyberkitchenapi.json")

# Assuming room and style are defined earlier
    Processed_data = {
    'room': room,
    'style': style,
    'image': pro  # Base64 encoded image
}
    os.remove(image_path)
    return Processed_data 

@app.route('/interior3', methods=['POST'])
def process3():
    additional = request.form['additional'] 
    image_file = request.files['image']
    image_path = "D:\What an AIdea!\ComfyUI_windows_portable\ComfyUI\input\example.png"
    image_file.save(image_path)
    pro=getimgpromptSINGLE("newinteriorapi.json",additional)

# Assuming room and style are defined earlier
    Processed_data = {

    'image': pro  # Base64 encoded image
}
    image_data = base64.b64decode(pro)
    
    # Convert bytes to a PIL Image
    image = Image.open(BytesIO(image_data))
    
    # Save the image to a file
    image.save("C:/Users/Admin/Desktop/app/output/hello.png")
    os.remove(image_path)
    return Processed_data 


@app.route('/getb2c', methods=['POST'])
def process2():
    room = request.form['room']
    print(room)
    style = request.form['style']
    print(style)
    image_file = request.files['image']
    image_path = "D:\What an AIdea!\ComfyUI_windows_portable\ComfyUI\input\example.png"
    image_file.save(image_path)
    if room=='pujaroom' and style=='modern':
        pro=getimg("modernpujab2c.json")
    if room=='pujaroom' and style=='neoclassical':
        pro=getimg("neoujab2c.json")
    if room=='pujaroom' and style=='Cyberpunk':
        pro=getimg("cyberpujab2c.json")
    elif room=='living-room' and style=='modern':
        pro=getimg("minimalistlivingb2c.json")
    elif room=='bedroom' and style=='modern':
        pro=getimg("minimalisticbedb2c.json")
    elif room=='kitchen' and style=='modern':
        pro=getimg("modernkitchenb2c.json")
    elif room=='living-room' and style=='neoclassical':
        pro=getimg("neolivingb2c.json")
    elif room=='bedroom' and style=='neoclassical':
        pro=getimg("neoclassicalbedb2c.json")
    elif room=='kitchen' and style=='neoclassical':
        pro=getimg("neokitchenb2c.json")
    elif room=='living-room' and style=='Cyberpunk':
        pro=getimg("cyberlivingb2c.json")
    elif room=='bedroom' and style=='Cyberpunk':
        pro=getimg("cyberbedb2c.json")
    elif room=='kitchen' and style=='Cyberpunk':
        pro=getimg("cyberkitchenb2c.json")

# Assuming room and style are defined earlier
    Processed_data = {
    'room': room,
    'style': style,
    'image': pro  # Base64 encoded image
}
    image_data = base64.b64decode(pro)
    
    # Convert bytes to a PIL Image
    image = Image.open(BytesIO(image_data))
    
    # Save the image to a file
    image.save("C:/Users/Admin/Desktop/app/output/hello.png")
    os.remove(image_path)
    return Processed_data 

@app.route('/getnew', methods=['POST'])
def process_imagenew():
    image_path = "D:\What an AIdea!\ComfyUI_windows_portable\ComfyUI\input\example.png"
    
    room = request.form['room']
    print(room)
    style = request.form['style']
    print(style)
    add = request.form['additional']
    image_file = request.files['image']
    
    image_file.save(image_path)
    pro=getimgprompt("newakashsir.json",room,style,add)
    Processed_data = {
    'room': room,
    'style': style,
    'image': pro  # Base64 encoded image
}
    image_data = base64.b64decode(pro)
    
    # Convert bytes to a PIL Image
    image = Image.open(BytesIO(image_data))
    
    # Save the image to a file
    image.save("C:/Users/Admin/Desktop/app/output/hello.png")
    os.remove(image_path)
    return Processed_data 

@app.route('/getproduct1', methods=['POST'])
def product1img():
    image_path = "D:\What an AIdea!\ComfyUI_windows_portable\ComfyUI\input\example.png"
    
    room = request.form['product']
    print(room)
    style = request.form['placement']
    print(style)
    add = request.form['background']
    image_file = request.files['image']
    
    image_file.save(image_path)
    pro=getimgproduct("sirproductapi.json",room,style,add)
    Processed_data = {
    'room': room,
    'style': style,
    'image': pro  # Base64 encoded image
}
    image_data = base64.b64decode(pro)
    
    # Convert bytes to a PIL Image
    image = Image.open(BytesIO(image_data))
    
    # Save the image to a file
    image.save("C:/Users/Admin/Desktop/app/output/hello.png")
    os.remove(image_path)
    return Processed_data 
@app.route('/getproduct2', methods=['POST'])
def product2img():
    image_path = "D:\What an AIdea!\ComfyUI_windows_portable\ComfyUI\input\example.png"
    
    room = request.form['product']
    print(room)
    add = request.form['background']
    image_file = request.files['image']
    
    image_file.save(image_path)
    pro=getimgproduct2("aryanproductapi.json",room,add)
    Processed_data = {
    'room': room,
    'style': add,
    'image': pro  # Base64 encoded image
}
    image_data = base64.b64decode(pro)
    
    # Convert bytes to a PIL Image
    image = Image.open(BytesIO(image_data))
    
    # Save the image to a file
    image.save("C:/Users/Admin/Desktop/app/output/hello.png")
    os.remove(image_path)
    return Processed_data 


@app.route('/feedbackproduct1', methods=['POST'])
def fdbckp1():
    feedback = request.form['feedback']
    input_image = request.files.get('input_image')
    add = request.form['backg']
    product = request.form['product']
    placed = request.form['placed']
    output_image_data = request.form.get('output_image')  # This will be a Base64 encoded string
    username=session['username']
    gentime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # This will be a Base64 encoded string

    # Define the CSV file path
    csv_file_path = 'C:/Users/Admin/Desktop/app/output/feedbackproduct1.csv'

    # Check if the file exists, if not, create with headers
    file_exists = os.path.isfile(csv_file_path)

    # Open the file in append mode ('a')
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created
        if not file_exists:
            writer.writerow(['username','time','product', 'placement', 'background','feedback', 'Image Input URL', 'Image Output URL'])

        # Save the input image to a directory, upload to Cloudinary and get the URL
        input_image_url = ""
        if input_image:
            input_image_path = os.path.join('C:/Users/Admin/Desktop/app/output', input_image.filename)
            input_image.save(input_image_path)
            uploaded_response = cloudinary.uploader.upload(input_image_path)
            input_image_url = uploaded_response['url']

        # Process the output image, save to Cloudinary and get the URL
        output_image_url = ""
        if output_image_data:
            # Check if the Base64 data contains the header
            if ',' in output_image_data:
                output_image_data = output_image_data.split(",")[1]
            # Decode the Base64 string to an image
            image_data = base64.b64decode(output_image_data)
            image = Image.open(BytesIO(image_data))
            output_image_path = 'temp_output_image.png'  # Temp path
            image.save(output_image_path)
            uploaded_response = cloudinary.uploader.upload(output_image_path)
            output_image_url = uploaded_response['url']  # Clean up the temp file

        # Write the data row
        writer.writerow([username,gentime,product, placed, add,feedback, input_image_url, output_image_url,])
    return jsonify({"message": "Feedback received successfully"}), 200



@app.route('/feedbackproduct2', methods=['POST'])
def fdbckp2():
    feedback = request.form['feedback']
    input_image = request.files.get('input_image')
    add = request.form['background']
    product = request.form['product']
    output_image_data = request.form.get('output_image')  # This will be a Base64 encoded string
    username=session['username']
    gentime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # This will be a Base64 encoded string

    # Define the CSV file path
    csv_file_path = 'C:/Users/Admin/Desktop/app/output/feedbackproduct2.csv'

    # Check if the file exists, if not, create with headers
    file_exists = os.path.isfile(csv_file_path)

    # Open the file in append mode ('a')
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created
        if not file_exists:
            writer.writerow(['username','time','product','background','feedback', 'Image Input URL', 'Image Output URL'])

        # Save the input image to a directory, upload to Cloudinary and get the URL
        input_image_url = ""
        if input_image:
            input_image_path = os.path.join('C:/Users/Admin/Desktop/app/output', input_image.filename)
            input_image.save(input_image_path)
            uploaded_response = cloudinary.uploader.upload(input_image_path)
            input_image_url = uploaded_response['url']

        # Process the output image, save to Cloudinary and get the URL
        output_image_url = ""
        if output_image_data:
            # Check if the Base64 data contains the header
            if ',' in output_image_data:
                output_image_data = output_image_data.split(",")[1]
            # Decode the Base64 string to an image
            image_data = base64.b64decode(output_image_data)
            image = Image.open(BytesIO(image_data))
            output_image_path = 'temp_output_image.png'  # Temp path
            image.save(output_image_path)
            uploaded_response = cloudinary.uploader.upload(output_image_path)
            output_image_url = uploaded_response['url']  # Clean up the temp file

        # Write the data row
        writer.writerow([username,gentime,product, add,feedback, input_image_url, output_image_url,])
    return jsonify({"message": "Feedback received successfully"}), 200
app.run(debug=True)
