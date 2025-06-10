# app.py
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/simon-ruth/Documents/thesis-ruth/pipeline/create-data/illumulus/webform_manual_feedback_data/annotations_Simon.db'
db = SQLAlchemy(app)

IMAGE_FOLDER = '/mnt/ceph/storage/data-tmp/current/majo2970/illumulus-label/img/'

class InputData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String, index=True)
    image_path = db.Column(db.String)
    story_string = db.Column(db.String)
    crux = db.Column(db.String)
    important_characters_and_objects = db.Column(db.Text)

class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String, index=True)
    image_path = db.Column(db.String)
    story_string = db.Column(db.String)
    crux = db.Column(db.String)
    important_characters_and_objects = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)

def get_next_concept(direction='forward', current_image_idx=None, current_concept_idx=None):
    input_data = InputData.query.order_by(InputData.id).all()
    total_images = len(input_data)
    print(f"[DEBUG] Direction: {direction}, Total Images: {total_images}")

    if not input_data:
        return None, None

    # Start from the beginning if no current position is given
    if current_image_idx is None or current_concept_idx is None:
        image_idx = 0
        concept_idx = 0
    else:
        image_idx = current_image_idx
        concept_idx = current_concept_idx

    if direction == 'forward':
        # Move to next concept, or next image if at end of concepts
        objects = json.loads(input_data[image_idx].important_characters_and_objects)
        if concept_idx + 1 < len(objects):
            concept_idx += 1
        else:
            image_idx += 1
            if image_idx >= total_images:
                return None, None
            concept_idx = 0
    elif direction == 'backward':
        # Move to previous concept, or previous image if at start of concepts
        if concept_idx > 0:
            concept_idx -= 1
        else:
            image_idx -= 1
            if image_idx < 0:
                return None, None
            objects = json.loads(input_data[image_idx].important_characters_and_objects)
            concept_idx = len(objects) - 1

    print(f"[DEBUG] Navigated to image_idx={image_idx}, concept_idx={concept_idx}")
    return image_idx, concept_idx

@app.route('/custom_images/<filename>')
def custom_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route('/')
def index():
    return redirect(url_for('annotate'))

@app.route('/annotate', methods=['GET', 'POST'])
def annotate():
    input_data = InputData.query.order_by(InputData.id).all()
    if not input_data:
        return "No input data available."

    # Get current indices from form or query params
    current_image_idx = request.args.get('image_idx', default=None, type=int)
    current_concept_idx = request.args.get('concept_idx', default=None, type=int)

    # If no indices provided, resume from last annotation
    if current_image_idx is None or current_concept_idx is None:
        last_ann = Annotation.query.order_by(Annotation.timestamp.desc()).first()
        if last_ann:
            # Find image index
            for idx, row in enumerate(input_data):
                if row.file_name == last_ann.file_name and row.image_path == last_ann.image_path:
                    current_image_idx = idx
                    # Find concept index (first not annotated, or last if all are annotated)
                    ann_objects = json.loads(last_ann.important_characters_and_objects)
                    for cidx, obj in enumerate(ann_objects):
                        if 'user_present' not in obj:
                            current_concept_idx = cidx
                            break
                    else:
                        current_concept_idx = len(ann_objects) - 1
                    break

    if request.method == 'POST':
        direction = 'backward' if request.form.get('action') == 'prev' else 'forward'
    else:
        direction = request.args.get('direction', 'forward')

    print(f"[DEBUG] Request method: {request.method}, Direction: {direction}")

    image_idx, concept_idx = get_next_concept(direction, current_image_idx, current_concept_idx)
    if image_idx is None:
        return render_template('done.html')

    row = input_data[image_idx]
    objects = json.loads(row.important_characters_and_objects)
    match = Annotation.query.filter_by(file_name=row.file_name, image_path=row.image_path).first()
    stored_objects = json.loads(match.important_characters_and_objects) if match else []

    if request.method == 'POST' and request.form.get('action') in ['next', 'prev']:
        present = request.form.get('present') == 'yes'
        print(f"[DEBUG] Annotating: present={present} at image_idx={image_idx}, concept_idx={concept_idx}")
        objects[concept_idx]['user_present'] = present

        if stored_objects:
            for i in range(min(len(objects), len(stored_objects))):
                if 'user_present' in stored_objects[i]:
                    objects[i]['user_present'] = stored_objects[i]['user_present']

        existing = Annotation.query.filter_by(file_name=row.file_name, image_path=row.image_path).first()
        if existing:
            print(f"[DEBUG] Updating existing annotation for {row.file_name}")
            existing.important_characters_and_objects = json.dumps(objects)
            existing.timestamp = datetime.utcnow()
        else:
            print(f"[DEBUG] Creating new annotation for {row.file_name}")
            ann = Annotation(
                file_name=row.file_name,
                image_path=row.image_path,
                story_string=row.story_string,
                crux=row.crux,
                important_characters_and_objects=json.dumps(objects),
                timestamp=datetime.utcnow()
            )
            db.session.add(ann)
        db.session.commit()

        # Pass new indices as query params
        return redirect(url_for('annotate', direction=direction, image_idx=image_idx, concept_idx=concept_idx))

    image_path = url_for('custom_image', filename=row.image_path)
    concept = objects[concept_idx]

    return render_template('index.html',
                           image_path=image_path,
                           story=row.story_string,
                           concept=concept,
                           image_num=image_idx + 1,
                           concept_num=concept_idx + 1,
                           total_images=len(input_data),
                           total_concepts=len(objects),
                           image_idx=image_idx,
                           concept_idx=concept_idx)

@app.route('/reset_db')
def reset_db():
    Annotation.query.delete()
    db.session.commit()
    return redirect(url_for('annotate'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
