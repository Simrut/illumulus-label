# app.py
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os
from pathlib import Path

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////mnt/ceph/storage/data-tmp/current/majo2970/illumulus-label/data/annotations.db'
db = SQLAlchemy(app)

IMAGE_FOLDER = '/mnt/ceph/storage/data-tmp/current/majo2970/illumulus-label/img/'

class InputData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String, index=True)
    image_path = db.Column(db.String)
    story_string = db.Column(db.String)
    crux = db.Column(db.String)
    important_characters_and_objects = db.Column(db.Text)  # JSON as string

class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String, index=True)
    image_path = db.Column(db.String)
    story_string = db.Column(db.String)
    crux = db.Column(db.String)
    important_characters_and_objects = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)

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

    if request.method == 'GET' and 'image_index' not in session:
        session['image_index'] = 0
        session['concept_index'] = 0

    image_idx = session.get('image_index', 0)
    concept_idx = session.get('concept_index', 0)

    if image_idx >= len(input_data):
        return render_template('done.html')

    row = input_data[image_idx]
    objects = json.loads(row.important_characters_and_objects)

    match = Annotation.query.filter_by(file_name=row.file_name, image_path=row.image_path).first()
    if match:
        stored_objects = json.loads(match.important_characters_and_objects)
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
                    session['image_index'] = image_idx - 1
                    row = input_data[image_idx - 1]
                    objects = json.loads(row.important_characters_and_objects)
                    match = Annotation.query.filter_by(file_name=row.file_name, image_path=row.image_path).first()
                    if match:
                        stored_objects = json.loads(match.important_characters_and_objects)
                        for i in range(min(len(objects), len(stored_objects))):
                            if 'user_present' in stored_objects[i]:
                                objects[i]['user_present'] = stored_objects[i]['user_present']
                    session['concept_index'] = len(objects) - 1
            return redirect(url_for('annotate'))

        present = request.form.get('present') == 'yes'
        objects[concept_idx]['user_present'] = present

        existing = Annotation.query.filter_by(file_name=row.file_name, image_path=row.image_path).first()
        if existing:
            existing.important_characters_and_objects = json.dumps(objects)
            existing.timestamp = datetime.utcnow()
        else:
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

        session['concept_index'] = concept_idx + 1
        if session['concept_index'] >= len(objects):
            session['image_index'] = image_idx + 1
            session['concept_index'] = 0

        return redirect(url_for('annotate'))

    concept = objects[concept_idx]
    image_path = url_for('custom_image', filename=row.image_path)

    return render_template('index.html',
                           image_path=image_path,
                           story=row.story_string,
                           concept=concept,
                           image_num=image_idx+1,
                           concept_num=concept_idx+1,
                           total_images=len(input_data),
                           total_concepts=len(objects))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
