import requests
from urllib.parse import quote
from functools import reduce
import operator
from itertools import chain, repeat, islice


class GitError(Exception):
    pass


def _get_json(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        raise GitError('GitHub request failed') from error


def intersperse(delimiter, seq):
    return list(
        islice(chain.from_iterable(zip(repeat(delimiter), seq)), 1, None))


def _get_from_dict(dataDict, mapList):
    return reduce(operator.getitem, mapList, dataDict)


def _append_in_dict(dataDict, mapList, value):
    _get_from_dict(dataDict, mapList[:-1]).append(value)


def _get_sha(author, repo):
    repository_url = (
        f'https://api.github.com/repos/{quote(author)}/{quote(repo)}'
    )
    repository = _get_json(repository_url)
    try:
        branch = repository['default_branch']
        branch_data = _get_json(
            f'{repository_url}/branches/{quote(branch, safe="")}'
        )
        return branch_data['commit']['commit']['tree']['sha'], branch
    except (KeyError, TypeError) as error:
        raise GitError('Invalid repository response') from error


def _get_git_tree(author, repo):
    sha, branch = _get_sha(author, repo)
    data = _get_json(
        f'https://api.github.com/repos/{quote(author)}/{quote(repo)}'
        f'/git/trees/{sha}?recursive=1'
    )
    try:
        return data['tree'], branch
    except (KeyError, TypeError) as error:
        raise GitError('Invalid repository tree') from error


def git_tree(repostring):
    try:
        author, repo = repostring.split("/")
    except ValueError as error:
        raise GitError('Invalid repository name') from error

    tokens, branch = _get_git_tree(author, repo)
    tree = {repo: {"files": [], "dirs": {}}}
    for token in tokens:
        if token["type"] == "tree" and "/" not in token["path"]:
            tree[repo]["dirs"].update({token["path"]: {}})
            tree[repo]["dirs"][token["path"]].update({"files": [], "dirs": {}})
        elif token["type"] == "tree" and "/" in token["path"]:
            temp_dict = {}
            a = list(reversed(token["path"].split("/")))
            for k in a[:-1]:
                temp_dict = {k: {"files": [], "dirs": temp_dict}}
            tree[repo]["dirs"][a[-1]]["dirs"] = temp_dict
        elif token["type"] == "blob":
            path = token["path"].split("/")
            if len(path) == 1:
                tree[repo]["files"].append(path[0])
            else:
                dict_path = [repo, "dirs"] + intersperse("dirs", path[:-1]) + [
                    "files", path[-1]]
                _append_in_dict(tree, dict_path, dict_path[-1])
    return tree, branch


def tree_to_urls(tree, repo, branch):
    urls = []
    base_url = f"https://raw.githubusercontent.com/{repo}/{branch}/"

    def traverse_tree(tree_dict, path=""):
        for key, value in tree_dict.items():
            if key == 'migrations':
                continue
            new_path = path + key + "/"
            files = value.get("files", [])  # получаем список файлов
            for file in files:
                if file.endswith(".py"):
                    urls.append(
                        base_url + new_path + file)  # формируем ссылку для каждого файла
            traverse_tree(value.get("dirs", {}),
                          new_path)  # рекурсивно обходим вложенные директории
    for i in tree[repo.split('/')[-1]]["files"]:
        urls.append(base_url + i)
    traverse_tree(
        tree[repo.split('/')[-1]][
            "dirs"])  # вызываем функцию для стартовой директории
    return urls
