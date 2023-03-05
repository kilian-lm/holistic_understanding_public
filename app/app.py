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

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] ='/run/secrets/service_account_key.json'
# os.environ['GOOGLE_APPLICATION_CREDENTIALS']
CLOUD_STORAGE_BUCKET = os.environ['CLOUD_STORAGE_BUCKET']


now = datetime.datetime.now()
timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")

# Create a class for handling PDF files
class PDFHandler:

    def __init__(self):
        # self.bucket_name = 'cloud_vision_221122'
        self.bucket_name = CLOUD_STORAGE_BUCKET
        self.client = storage.Client()


    def filter_and_save_to_csv(self, lst, email, save_to_bucket, filename):
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
        with open(os.path.join('temp_csv', filename), 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(['product', 'price', 'email'])
            writer.writerows(filtered_lst)

        # Upload the CSV file to a GCS bucket
        if save_to_bucket:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_filename(os.path.join('temp_csv', filename))

        return filename

    def process_pdf(self, file_path, email, save_to_bucket, filename):
        # Open the PDF file
        pdf_file = open(file_path, 'rb')
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        # Extract the text from the PDF file
        # Extract the text from the PDF file
        text = ''
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        lines = text.split('\n')

        # Filter and save the data to a CSV file
        filename = self.filter_and_save_to_csv(lines, email, save_to_bucket, filename)

        # Close the PDF file
        pdf_file.close()

        return filename


pdf_handler = PDFHandler()


@app.route('/', methods=['GET', 'POST'])
def upload_pdf():
    csv_file = None
    csv_state = None
    if request.method == 'POST':
        pdf_file = request.files['pdf_file']
        email = request.form.get('email')
        save_to_bucket = request.form.get('save_to_bucket')

        # set the filename as the timestamp
        # now = datetime.datetime.now()
        # timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
        filename = timestamp + '.csv'

        # Save the pdf to temp_pdf directory
        pdf_file.save(os.path.join('temp_pdf', pdf_file.filename))

        # process the pdf and save the csv to temp
        save_to_bucket = False

        # process the pdf and save the csv to temp_csv directory
        csv_file = pdf_handler
        csv_file = pdf_handler.process_pdf(os.path.join('temp_pdf', pdf_file.filename), email, save_to_bucket,
                                           filename)

        # Check if save_to_bucket checkbox is checked before uploading the files to GCS
        if save_to_bucket == 'on':
            # Upload csv to GCS bucket
            bucket = pdf_handler.client.bucket(pdf_handler.bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_filename(os.path.join('temp_csv', filename))

            # Upload pdf to GCS bucket
            blob = bucket.blob(pdf_file.filename)
            blob.upload_from_filename(os.path.join('temp_pdf', pdf_file.filename))


        if save_to_bucket == 'on':
            csv_state = "processing"
        else:
            csv_state = "Ihre Daten wurden NICHT gespeichert, viel Spass beim Analysieren"

            return render_template('upload.html', csv_file=filename, csv_state=csv_state)

    else:
        return render_template('upload.html')





@app.route('/download_csv')
def download_csv():
    # set the filename as the timestamp
    filename = timestamp + '.csv'
    # Always read from temp directory, even if the checkbox is checked
    save_to_bucket = False
    # Check if save_to_bucket checkbox is checked before downloading the file
    if request.args.get('save_to_bucket') == 'on':
        # Download csv from GCS bucket
        bucket = pdf_handler.client.bucket(pdf_handler.bucket_name)
        blob = bucket.blob(filename)
        blob.download_to_filename(os.path.join('temp_csv', filename))
        save_to_bucket = True

    if save_to_bucket:
        csv_state = "processing"
    else:
        csv_state = "Ihre Daten wurden NICHT gespeichert, viel Spass beim Analysieren"

    # Create a thread to wait for the download button to be clicked
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
    # Delete temp directories before starting the server
    shutil.rmtree('temp_csv', ignore_errors=True)
    shutil.rmtree('temp_pdf', ignore_errors=True)
    os.makedirs('temp_csv', exist_ok=True)
    os.makedirs('temp_pdf', exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
# app.run(debug=False)

# if __name__ == "__main__":
#     app.run(host="0.0.0.0")