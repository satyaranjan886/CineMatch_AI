# Generated manually for horizontal-scaling model registry fields.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recommendations", "0004_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="collaborativemodelartifact",
            name="model_name",
            field=models.CharField(
                db_index=True, default="collaborative_als", max_length=64
            ),
        ),
        migrations.AddField(
            model_name="collaborativemodelartifact",
            name="dataset_version",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddIndex(
            model_name="collaborativemodelartifact",
            index=models.Index(
                fields=["model_name", "-trained_at"],
                name="cf_artifact_name_trained_idx",
            ),
        ),
    ]
