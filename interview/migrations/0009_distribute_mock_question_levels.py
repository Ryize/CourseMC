from collections import defaultdict

from django.db import migrations


LEVELS = ('junior', 'middle', 'senior')


def distribute_mock_levels(apps, schema_editor):
    Question = apps.get_model('interview', 'InterviewQuestion')
    groups = defaultdict(list)
    questions = (
        Question.objects
        .filter(use_in_mock=True)
        .order_by('complexity', 'title', 'pk')
    )
    for question in questions:
        # Framework questions must be balanced inside each framework. The other
        # sections are selected as a whole, regardless of their category.
        group_key = (
            question.mock_section,
            question.theme_id if question.mock_section == 'framework' else None,
        )
        groups[group_key].append(question)

    changed = []
    for group in groups.values():
        edge_size = len(group) // 3
        senior_start = len(group) - edge_size
        for index, question in enumerate(group):
            if index < edge_size:
                level = LEVELS[0]
            elif index >= senior_start:
                level = LEVELS[2]
            else:
                level = LEVELS[1]
            if question.mock_level != level:
                question.mock_level = level
                changed.append(question)
    if changed:
        Question.objects.bulk_update(changed, ('mock_level',))


def reset_mock_levels(apps, schema_editor):
    Question = apps.get_model('interview', 'InterviewQuestion')
    Question.objects.filter(use_in_mock=True).update(mock_level='junior')


class Migration(migrations.Migration):

    dependencies = [
        ('interview', '0008_interviewquestion_mock_level_mockinterview_level_and_more'),
    ]

    operations = [
        migrations.RunPython(distribute_mock_levels, reset_mock_levels),
    ]
