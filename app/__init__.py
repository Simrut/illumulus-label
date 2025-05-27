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
    if request.method == 'GET':
        image_idx = 0
        concept_idx = 0

        if os.path.exists(OUTPUT_CSV):
            output_df = pd.read_csv(OUTPUT_CSV)
            if not output_df.empty:
                last_row = output_df.iloc[-1]
                last_file = last_row['file_name']

                matched_rows = input_data[input_data['file_name'] == last_file]
                if not matched_rows.empty:
                    image_idx = matched_rows.index[0]
                    objects = json.loads(last_row['important_characters_and_objects'])
                    for i, obj in enumerate(objects):
                        if 'user_present' not in obj:
                            concept_idx = i
                            break
                    else:
                        image_idx += 1
                        concept_idx = 0

        session['image_index'] = int(image_idx)
        session['concept_index'] = int(concept_idx)

    image_idx = session.get('image_index', 0)
    concept_idx = session.get('concept_index', 0)

    if image_idx >= len(input_data):
        return render_template('done.html')

    row = input_data.iloc[image_idx]


    # Keep full row from input_data but update only `important_characters_and_objects` if already annotated
    if os.path.exists(OUTPUT_CSV):
        output_df = pd.read_csv(OUTPUT_CSV)
        matched = output_df[output_df['file_name'] == row['file_name']]
        if not matched.empty:
            annotated_row = matched.iloc[0]
            row['important_characters_and_objects'] = annotated_row['important_characters_and_objects']

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
            match_idx = output_df[output_df['file_name'] == row['file_name']].index

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
