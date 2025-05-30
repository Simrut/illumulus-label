from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from pathlib import Path
import pandas as pd
import os
import json
from datetime import datetime

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'supersecretkey'

INPUT_CSV = '/mnt/ceph/storage/data-tmp/current/majo2970/illumulus-label/labeled_data_with_entities.csv'
OUTPUT_CSV = '/mnt/ceph/storage/data-tmp/current/majo2970/illumulus-label/data/annotations.csv'
IMAGE_FOLDER = '/mnt/ceph/storage/data-tmp/current/majo2970/illumulus-label/img/'

input_data = pd.read_csv(INPUT_CSV)

@app.route('/custom_images/<filename>')
def custom_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route('/')
def index():
    return redirect(url_for('annotate'))

@app.route('/annotate', methods=['GET', 'POST'])
def annotate():
    if request.method == 'GET' and (not os.path.exists(OUTPUT_CSV) or 'image_index' not in session):
        image_idx = 0
        concept_idx = 0

        if os.path.exists(OUTPUT_CSV):
            output_df = pd.read_csv(OUTPUT_CSV)
            if not output_df.empty:
                last_row = output_df.iloc[-1]
                last_file = last_row['file_name']

                matched_rows = input_data[input_data['file_name'] == last_file]
                found_next = False

                for idx in matched_rows.index:
                    row = input_data.loc[idx]
                    annotated_row = output_df[(output_df['file_name'] == last_file) & (output_df['image_path'] == row['image_path'])]

                    base_objects = json.loads(row['important_characters_and_objects'])
                    objects = base_objects.copy()

                    if not annotated_row.empty:
                        stored_objects = json.loads(annotated_row.iloc[0]['important_characters_and_objects'])
                        for i in range(min(len(objects), len(stored_objects))):
                            if 'user_present' in stored_objects[i]:
                                objects[i]['user_present'] = stored_objects[i]['user_present']

                    for i, obj in enumerate(objects):
                        if 'user_present' not in obj:
                            image_idx = idx
                            concept_idx = i
                            found_next = True
                            break
                    if found_next:
                        break

                if not found_next:
                    next_idx = matched_rows.index[-1] + 1
                    if next_idx < len(input_data):
                        image_idx = next_idx
                        concept_idx = 0

        session['image_index'] = int(image_idx)
        session['concept_index'] = int(concept_idx)

    image_idx = session.get('image_index', 0)
    concept_idx = session.get('concept_index', 0)

    if image_idx >= len(input_data):
        return render_template('done.html')

    row = input_data.iloc[image_idx]
    objects = json.loads(row['important_characters_and_objects'])

    if os.path.exists(OUTPUT_CSV):
        output_df = pd.read_csv(OUTPUT_CSV)
        match = output_df[(output_df['file_name'] == row['file_name']) & (output_df['image_path'] == row['image_path'])]
        if not match.empty:
            stored_objects = json.loads(match.iloc[0]['important_characters_and_objects'])
            for i in range(min(len(objects), len(stored_objects))):
                if 'user_present' in stored_objects[i]:
                    objects[i]['user_present'] = stored_objects[i]['user_present']

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'prev':
            if concept_idx > 0:
                session['concept_index'] = concept_idx - 1
            else:
                if image_idx > 0:
                    image_idx -= 1
                    row = input_data.iloc[image_idx]
                    objects = json.loads(row['important_characters_and_objects'])

                    if os.path.exists(OUTPUT_CSV):
                        output_df = pd.read_csv(OUTPUT_CSV)
                        match = output_df[(output_df['file_name'] == row['file_name']) & (output_df['image_path'] == row['image_path'])]
                        if not match.empty:
                            stored_objects = json.loads(match.iloc[0]['important_characters_and_objects'])
                            for i in range(min(len(objects), len(stored_objects))):
                                if 'user_present' in stored_objects[i]:
                                    objects[i]['user_present'] = stored_objects[i]['user_present']

                    session['image_index'] = image_idx
                    session['concept_index'] = len(objects) - 1
            return redirect(url_for('annotate'))

        present = request.form.get('present') == 'yes'
        objects[concept_idx]['user_present'] = present

        output_row = {
            'file_name': row['file_name'],
            'image_path': row['image_path'],
            'story_string': row['story_string'],
            'crux': row['crux'],
            'important_characters_and_objects': json.dumps(objects),
            'timestamp': datetime.utcnow().isoformat()
        }

        Path(Path(OUTPUT_CSV).parent).mkdir(parents=True, exist_ok=True)

        if os.path.exists(OUTPUT_CSV):
            output_df = pd.read_csv(OUTPUT_CSV)
            match_idx = output_df[(output_df['file_name'] == row['file_name']) & (output_df['image_path'] == row['image_path'])].index

            if not match_idx.empty:
                output_df.loc[match_idx[0]] = output_row
            else:
                output_df = pd.concat([output_df, pd.DataFrame([output_row])], ignore_index=True)
        else:
            output_df = pd.DataFrame([output_row])

        output_df.to_csv(OUTPUT_CSV, index=False)

        session['concept_index'] = concept_idx + 1

        if session['concept_index'] >= len(objects):
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
