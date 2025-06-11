from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

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
    object_name = db.Column(db.String)
    user_present = db.Column(db.Boolean, default=None, nullable=True)

class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String, index=True)
    image_path = db.Column(db.String)
    object_name = db.Column(db.String)
    user_present = db.Column(db.Boolean, default=None, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

def get_annotatable(direction='forward', current_id=None):
    query = InputData.query.order_by(InputData.id)
    records = query.all()
    ids = [r.id for r in records]

    if not ids:
        return None

    if current_id is None:
        return ids[0] if direction == 'forward' else ids[-1]

    try:
        idx = ids.index(current_id)
        next_idx = idx + 1 if direction == 'forward' else idx - 1

        if next_idx < 0:
            return ids[0]  # Stay on first image
        elif next_idx >= len(ids):
            return None  # End of images
        else:
            return ids[next_idx]
    except ValueError:
        return None


@app.route('/custom_images/<filename>')
def custom_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route('/')
def index():
    return redirect(url_for('annotate'))

@app.route('/annotate', methods=['GET', 'POST'])
def annotate():
    current_id = request.args.get('id', type=int)
    direction = request.form.get('action') if request.method == 'POST' else request.args.get('direction', 'forward')

    if request.method == 'POST':
        present = request.form.get('present') == 'yes'
        input_id = request.form.get('input_id')

        if input_id is None:
            return "Missing input_id", 400

        input_id = int(input_id)
        record = InputData.query.get(input_id)

        if record:
            ann = Annotation.query.filter_by(file_name=record.file_name, image_path=record.image_path, object_name=record.object_name).first()
            if not ann:
                ann = Annotation(
                    file_name=record.file_name,
                    image_path=record.image_path,
                    object_name=record.object_name,
                )
                db.session.add(ann)

            ann.user_present = present
            ann.timestamp = datetime.utcnow()
            db.session.commit()
            current_id = input_id

    next_id = get_annotatable(direction, current_id)
    if next_id is None:
        return render_template('done.html')

    row = InputData.query.get(next_id)
    annotated = Annotation.query.filter_by(file_name=row.file_name, image_path=row.image_path, object_name=row.object_name).first()
    image_path = url_for('custom_image', filename=row.image_path)

    total_concepts = InputData.query.count()
    total_images = len(set((r.file_name, r.image_path) for r in InputData.query.all()))
    concept_num = InputData.query.order_by(InputData.id).filter(InputData.id <= row.id).count()

    seen_images = set()
    image_num = 0
    for r in InputData.query.order_by(InputData.id):
        key = (r.file_name, r.image_path)
        if key not in seen_images:
            image_num += 1
            seen_images.add(key)
        if r.id == row.id:
            break

    return render_template('index.html',
                           image_path=image_path,
                           story=row.story_string,
                           concept={'name': row.object_name},
                           image_idx=row.id,
                           present=annotated.user_present if annotated else None,
                           input_id=row.id,
                           image_num=image_num,
                           concept_num=concept_num,
                           total_images=total_images,
                           total_concepts=total_concepts)

# @app.route('/reset_db')
# def reset_db():
#     Annotation.query.delete()
#     db.session.commit()
#     return redirect(url_for('annotate'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
