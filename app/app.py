from flask import Flask, request, render_template, send_file
import PyPDF2
import re
import csv
from google.cloud import storage
import os
import datetime
import shutil
import threading
import gunicorn


# Create the Flask app
app = Flask(__name__)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] ='/run/secrets/*****'
# os.environ['GOOGLE_APPLICATION_CREDENTIALS']
CLOUD_STORAGE_BUCKET = os.environ['CLOUD_STORAGE_BUCKET']


now = datetime.datetime.now()
timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")

class App:
    def __init__(self):
        self.client = storage.Client()
        self.bucket_name = 'cloud_vision_221122'
        self.bucket = self.client.bucket(self.bucket_name)

    def filter_and_save_to_csv(self, lst, email, save_to_bucket, timestamp):
        # Create a regular expression pattern to match the desired strings
        pattern = r'(\w+)\s*(\d+,\d+)\s*B'

        # Create an empty list to store the filtered strings
        filtered_lst = []

        # Iterate through the list and filter the strings that match the pattern
        for s in lst:
            match = re.search(pattern, s)
            if match:
                filtered_lst.append(match.groups())

        # Convert the price to a float and replace the comma with a period
        for i in range(len(filtered_lst)):
            product, price_str = filtered_lst[i]
            price = float(price_str.replace(',', '.'))
            filtered_lst[i] = (product, price, email)

        # Save the filtered list to a CSV file with three columns: "product", "price" and "email"
        filename = os.path.join('temp_csv', f"{timestamp}.csv")

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            if email:
                writer.writerow(['product', 'price', 'email'])
            else:
                writer.writerow(['product', 'price'])
            writer.writerows(filtered_lst)

        # Upload the CSV file to a GCS bucket
        if save_to_bucket:
            blob = self.bucket.blob(filename)
            blob.upload_from_filename(filename)

        return filename

    def process_pdf(self, file_path, email, save_to_bucket, timestamp):
        # Open the PDF file
        pdf_file = open(file_path, 'rb')
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        # Extract the text from the PDF file
        text = ''
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        lines = text.split('\n')

        # Filter and save the data to a CSV file
        filename = self.filter_and_save_to_csv(lines, email, save_to_bucket, timestamp)

        # Close the PDF file
        pdf_file.close()

        return filename


app_obj = App()


import os
import glob

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        pdf_file = request.files['pdf_file']
        save_to_bucket = request.form.get('save_to_bucket')
        email = request.form.get('email')

        # Save PDF file to server
        pdf_filename = os.path.join('temp_pdf', 'pdf_file.pdf')
        pdf_file.save(pdf_filename)

        # Process PDF file and filter data

        csv_filename = app_obj.process_pdf(pdf_filename, email, save_to_bucket, timestamp)

        # Set state to display to user
        if save_to_bucket:
            csv_state = 'CSV file uploaded to GCS bucket. Thanks a lot:) '
        else:
            csv_state = 'CSV file is not uploade. Happy Analyzing'

        return render_template('upload.html', csv_file=csv_filename, csv_state=csv_state)

    return render_template('upload.html')


@app.route('/download_csv')
def download_csv():
    # Get the filename of the CSV file from the temp_csv folder
    global timestamp
    filename = f"{timestamp}.csv"
    # return send_file(filename, as_attachment=True)
    def wait_for_download():
        while True:
            if os.path.exists(os.path.join('temp_csv', filename)):
                break

    download_thread = threading.Thread(target=wait_for_download)
    download_thread.start()

    # Send the file as an attachment
    response = send_file(os.path.join('temp_csv', filename), as_attachment=True)

    # Wait for the download thread to finish
    download_thread.join()

    # Delete temp directories
    shutil.rmtree('temp_csv', ignore_errors=True)
    shutil.rmtree('temp_pdf', ignore_errors=True)
    os.makedirs('temp_csv', exist_ok=True)
    os.makedirs('temp_pdf', exist_ok=True)

    return response


@app.route('/mission')
def mission():
    return render_template('mission.html')

@app.route('/legal_notice')
def legal_notice():
    return render_template('legal_notice.html')



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
