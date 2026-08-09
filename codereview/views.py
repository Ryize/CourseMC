from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from Course.models import Student

from .cognetive_counter import get_project_info
from .forms import ProjectForReviewForm
from .git_urls import GitError
from .models import ProjectForReview


def learned_student(request):
    student = Student.objects.filter(name=request.user.username).first()
    if student is None or not student.is_learned:
        raise PermissionDenied
    return student


@login_required
def send_review(request):
    user = learned_student(request)
    form = ProjectForReviewForm(request.POST or None)

    if request.method != 'POST' or not form.is_valid():
        return render(
            request,
            'codereview/send_review.html',
            context={'form': form},
        )

    category = form.cleaned_data['category']
    github = form.cleaned_data['github']
    comment = form.cleaned_data['comment'] or 'Нет комментария'
    existing_review = (
        ProjectForReview.objects
        .filter(user=user, github=github, status=False)
        .order_by('-pk')
        .first()
    )
    if existing_review:
        messages.info(
            request,
            'Этот репозиторий уже ожидает проверки.',
        )
        return redirect('review_my', pk=existing_review.pk)

    try:
        stats = get_project_info(form.repository_name)
    except (GitError, ValueError):
        form.add_error(
            'github',
            'Не удалось прочитать репозиторий. Проверьте ссылку и доступность GitHub.',
        )
        return render(
            request,
            'codereview/send_review.html',
            context={'form': form},
        )

    meets_requirements = (
        category.min_cognetive
        <= stats['all_cognetive']
        <= category.max_cognetive
        and stats['all_size'] >= category.min_lines
    )
    if not meets_requirements:
        form.add_error(
            None,
            f'Проект пока не соответствует категории: нужно от '
            f'{category.min_lines} строк и сложность '
            f'{category.min_cognetive}–{category.max_cognetive}.',
        )
        return render(
            request,
            'codereview/send_review.html',
            context={'form': form},
        )

    review = ProjectForReview.objects.create(
        category=category,
        github=github,
        comment=comment,
        user=user,
        lines=stats['all_size'],
        cognetive=stats['all_cognetive'],
    )
    messages.success(request, 'Проект отправлен на проверку.')
    return redirect('review_my', pk=review.pk)


@login_required
def list_review(request):
    if request.user.is_staff:
        reviews = ProjectForReview.objects.all()
    else:
        user = learned_student(request)
        reviews = ProjectForReview.objects.filter(user=user)

    reviews = (
        reviews
        .select_related('category', 'user')
        .prefetch_related('code_review')
        .order_by('-pk')
    )
    page_obj = Paginator(reviews, 20).get_page(request.GET.get('page'))
    return render(request, 'codereview/list_review.html',
                  context={'reviews': page_obj, 'page_obj': page_obj})


@login_required
def my_review(request, pk):
    review = get_object_or_404(
        ProjectForReview.objects
        .select_related('category', 'user')
        .prefetch_related('code_review'),
        pk=pk,
    )
    if not request.user.is_staff:
        user = learned_student(request)
        if review.user != user:
            raise PermissionDenied

    return render(request, 'codereview/my_review.html',
                  context={'review': review})
