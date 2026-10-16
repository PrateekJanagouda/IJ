from django.db import migrations

GENRES = [
    "Acoustic", "Blues", "Bollywood", "Classical", "Comedy", "Contemporary Dance", "Country",
    "Electronic", "Folk", "Hip Hop", "Indie", "Jazz", "Metal", "Pop", "Punk", "R&B", "Reggae",
    "Rock", "Soul", "Spoken Word", "Theatre", "World",
]
SKILLS = [
    "Bass", "Beatboxing", "DJing", "Dancing", "Drums", "Guitar", "Hosting / MC", "Keys",
    "Music Production", "Percussion", "Poetry", "Rapping", "Singing", "Sound Engineering",
    "Stand-up", "Strings", "Violin", "Wind Instruments",
]


def slug(name):
    return (
        name.lower().replace("&", "and").replace("/", " ").replace("-", " ")
        .replace("  ", " ").strip().replace(" ", "-")
    )


def seed(apps, schema_editor):
    Genre = apps.get_model("profiles", "Genre")
    Skill = apps.get_model("profiles", "Skill")
    for name in GENRES:
        Genre.objects.get_or_create(slug=slug(name), defaults={"name": name})
    for name in SKILLS:
        Skill.objects.get_or_create(slug=slug(name), defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("profiles", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
