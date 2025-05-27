# app.py

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from pathlib import Path
import pandas as pd
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

INPUT_CSV = '/home/simon-ruth/Documents/thesis-ruth/data_sources/illumulus-examples/CRUX_labeled_dataset/labeled_stories/labeled_data_with_entities.csv'
OUTPUT_CSV = 'data/annotations.csv'
IMAGE_FOLDER = '/home/simon-ruth/Documents/thesis-ruth/data_sources/illumulus-examples/illumulus-stories/img/'

input_data = pd.read_csv(INPUT_CSV)

@app.route('/custom_images/<filename>')
def custom_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route('/')
def index():
    session['image_index'] = 0
    session['concept_index'] = 0
    return redirect(url_for('annotate'))

@app.route('/annotate', methods=['GET', 'POST'])
def annotate():
    image_idx = session.get('image_index', 0)
    concept_idx = session.get('concept_index', 0)

    if image_idx >= len(input_data):
        return render_template('done.html')

    row = input_data.iloc[image_idx]
    objects = json.loads(row['important_characters_and_objects'])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'prev':
            if concept_idx > 0:
                session['concept_index'] = concept_idx - 1
            elif image_idx > 0:
                session['image_index'] = image_idx - 1
                previous_row = input_data.iloc[image_idx - 1]
                previous_objects = json.loads(previous_row['important_characters_and_objects'])
                session['concept_index'] = len(previous_objects) - 1
            return redirect(url_for('annotate'))

        present = request.form.get('present') == 'yes'
        objects[concept_idx]['user_present'] = present

        session['concept_index'] = concept_idx + 1

        if session['concept_index'] >= len(objects):
            output_row = {
                'file_name': row['file_name'],
                'image_path': row['image_path'],
                'story_string': row['story_string'],
                'crux': row['crux'],
                'important_characters_and_objects': json.dumps(objects),
                'timestamp': datetime.utcnow().isoformat()
            }

            Path(Path(OUTPUT_CSV).parent).mkdir(parents=True, exist_ok=True)

            if not os.path.exists(OUTPUT_CSV):
                pd.DataFrame([output_row]).to_csv(OUTPUT_CSV, index=False)
            else:
                pd.DataFrame([output_row]).to_csv(OUTPUT_CSV, mode='a', header=False, index=False)

            session['image_index'] = image_idx + 1
            session['concept_index'] = 0

        return redirect(url_for('annotate'))

    concept = objects[concept_idx]
    image_path = url_for('custom_image', filename=row["image_path"])

    return render_template('index.html',
                           image_path=image_path,
                           story=row['story_string'],
                           concept=concept,
                           image_num=image_idx+1,
                           concept_num=concept_idx+1,
                           total_images=len(input_data),
                           total_concepts=len(objects))

if __name__ == '__main__':
    app.run(debug=True)
