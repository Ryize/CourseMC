from threading import Thread

import radon.complexity as radon_complexity

import requests

from .git_urls import git_tree, tree_to_urls

project_stats = {
    'all_cognetive': 0,
    'all_size': 0,
}


# Функция для подсчета когнитивной сложности проекта
def calculate_cognitive_complexity(content):
    total_complexity = 0
    total_file_size = len(content.split('\n'))
    result = radon_complexity.cc_visit(content)
    for item in result:
        total_complexity += item.complexity

    return total_complexity, total_file_size


def _get_project_info(url):
    data = requests.get(url).text
    complexity = calculate_cognitive_complexity(data)
    all_cognetive = complexity[0]
    all_size = complexity[1]

    project_stats['all_cognetive'] += all_cognetive
    project_stats['all_size'] += all_size


def get_project_info(project):
    project_stats['all_cognetive'] = 0
    project_stats['all_size'] = 0
    tree = git_tree(project)
    urls = tree_to_urls(tree, project)

    threads = []
    for url in urls:
        threads.append(Thread(target=_get_project_info, args=(url,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return project_stats
