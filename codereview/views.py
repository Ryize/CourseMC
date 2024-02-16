from django.shortcuts import render, redirect
from Course.models import Student
from .cognetive_counter import get_project_info
from .git_urls import GitError
from .models import ProjectCategories, ProjectForReview, CodeReview


def send_review(request):
    user = Student.objects.filter(name=request.user.username).first()
    if not user or not user.is_learned:
        return redirect('home')
    if request.method == 'GET':
        context = {
            'categories': ProjectCategories.objects.all(),
        }
        return render(request, 'codereview/send_review.html', context=context)
    category = ProjectCategories.objects.filter(
        title=request.POST.get('category')).first()
    github = request.POST.get('github')
    comment = request.POST.get('comment')
    if not comment:
        comment = 'Нет комментария'
    try:
        github_list = github.split('/')
        stats = get_project_info(f'{github_list[3]}/{github_list[4]}')
    except (GitError, IndexError):
        context = {
            'categories': ProjectCategories.objects.all(),
            'error': 'Неверная ссылка на репозиторий!'
        }
        return render(request, 'codereview/send_review.html', context=context)
    if not (category.min_cognetive < stats['all_cognetive'] <
            category.max_cognetive
            and
            category.min_lines < stats['all_size']):
        context = {
            'categories': ProjectCategories.objects.all(),
            'error': f'Недостаточно строк кода'
                     f'(от {category.min_lines})/сложности '
                     f'проекта({category.min_cognetive}-'
                     f'{category.max_cognetive})'
        }
        return render(request, 'codereview/send_review.html', context=context)
    review = ProjectForReview.objects.create(category=category,
                                             github=github,
                                             comment=comment,
                                             user=user,
                                             lines=stats['all_size'],
                                             cognetive=stats['all_cognetive'],
                                             )
    return redirect('review_my', pk=review.pk)


def list_review(request):
    user = Student.objects.filter(name=request.user.username).first()
    if not user or not user.is_learned:
        return redirect('home')
    if request.user.is_staff:
        my_reviews = ProjectForReview.objects.order_by('-pk').all()
    else:
        my_reviews = ProjectForReview.objects.filter(user=user).order_by(
            '-pk').all()
    return render(request, 'codereview/list_review.html',
                  context={'reviews': my_reviews})


def my_review(request, pk):
    user = Student.objects.filter(name=request.user.username).first()
    if not user or not user.is_learned:
        return redirect('home')
    review = ProjectForReview.objects.filter(pk=pk).first()
    if not review or review.user != user:
        return redirect('review_list')
    return render(request, 'codereview/my_review.html',
                  context={'review': review})


def check_review(request):
    if not request.user.is_staff:
        return redirect('home')
    if request.method == 'GET':
        projects = ProjectForReview.objects.filter(status=False).all()
        return render(request, 'codereview/check_review.html',
                      context={'projects': projects})
    project = ProjectForReview.objects.filter(
        github=request.POST.get('github')).first()
    status = request.POST.get('status')
    review = request.POST.get('review')
    CodeReview.objects.create(project=project, status=status, review=review)
    project.status = True
    project.save()
    return redirect('home')
