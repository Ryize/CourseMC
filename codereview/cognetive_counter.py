from concurrent.futures import ThreadPoolExecutor

import radon.complexity as radon_complexity
import requests

from .git_urls import git_tree, tree_to_urls



def calculate_cognitive_complexity(content):
    total_complexity = 0
    total_file_size = len(content.split('\n'))
    result = radon_complexity.cc_visit(content)
    for item in result:
        total_complexity += item.complexity

    return total_complexity, total_file_size


def _get_project_info(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return calculate_cognitive_complexity(response.text)


def get_project_info(project):
    tree, branch = git_tree(project)
    urls = tree_to_urls(tree, project, branch)
    if not urls:
        return {'all_cognetive': 0, 'all_size': 0}

    try:
        with ThreadPoolExecutor(max_workers=min(8, len(urls))) as executor:
            file_stats = list(executor.map(_get_project_info, urls))
    except (requests.RequestException, SyntaxError) as error:
        raise ValueError('Could not analyse repository') from error

    return {
        'all_cognetive': sum(item[0] for item in file_stats),
        'all_size': sum(item[1] for item in file_stats),
    }
