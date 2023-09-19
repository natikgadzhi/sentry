# Generated by Django 3.2.20 on 2023-09-12 16:50

import django.db.models.deletion
from django.db import migrations, models

import sentry.db.models.fields.foreignkey
from sentry.new_migrations.migrations import CheckedMigration


class Migration(CheckedMigration):
    # This flag is used to mark that a migration shouldn't be automatically run in production. For
    # the most part, this should only be used for operations where it's safe to run the migration
    # after your code has deployed. So this should not be used for most operations that alter the
    # schema of a table.
    # Here are some things that make sense to mark as dangerous:
    # - Large data migrations. Typically we want these to be run manually by ops so that they can
    #   be monitored and not block the deploy for a long period of time while they run.
    # - Adding indexes to large tables. Since this can take a long time, we'd generally prefer to
    #   have ops run this and not block the deploy. Note that while adding an index is a schema
    #   change, it's completely safe to run the operation after the code has deployed.
    is_dangerous = True

    dependencies = [
        ("sentry", "0548_add_is_unclaimed_boolean_to_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupsubscription",
            name="team",
            field=sentry.db.models.fields.foreignkey.FlexibleForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, to="sentry.team"
            ),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="groupsubscription",
                    name="user_id",
                    field=sentry.db.models.fields.hybrid_cloud_foreign_key.HybridCloudForeignKey(
                        "sentry.User", db_index=True, null=True, on_delete="CASCADE"
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    reverse_sql="""
                    ALTER TABLE "sentry_groupsubscription" ALTER COLUMN "user_id" SET NOT NULL;
                    """,
                    sql="""
                    ALTER TABLE "sentry_groupsubscription" ALTER COLUMN "user_id" DROP NOT NULL;
                    """,
                    hints={"tables": ["sentry_groupsubscription"]},
                )
            ],
        ),
        migrations.AlterUniqueTogether(
            name="groupsubscription",
            unique_together={("group", "team"), ("group", "user_id")},
        ),
        migrations.AddConstraint(
            model_name="groupsubscription",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(("team_id__isnull", False), ("user_id__isnull", True)),
                    models.Q(("team_id__isnull", True), ("user_id__isnull", False)),
                    _connector="OR",
                ),
                name="subscription_team_or_user_check",
            ),
        ),
    ]
