from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import CreateView, DetailView, ListView

from .forms import PostForm
from .models import *


class PostCreateView(LoginRequiredMixin, CreateView):
    form_class = PostForm
    template_name = "blog/post_create.html"
    redirect_field_name = "redirect_to"

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args)
        form.instance.author = self.request.user
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['descry'] = Post.objects.filter(is_displayed=False).all()
        return context


class PostListView(ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"

    def get_queryset(self):
        if self.request.GET:
            search_query = self.request.GET.get("search")
            author = self.request.GET.get("author")
            if author:
                return (
                    Post.objects.filter(
                        Q(is_displayed=True)
                        & (
                            Q(author__username__icontains=author)
                        )
                    )
                    .prefetch_related("categories")
                    .all()
                )
            if search_query:
                return set(
                    Post.objects.filter(
                        Q(is_displayed=True)
                        & (
                                Q(title__icontains=search_query)
                                | Q(description__icontains=search_query)
                                | Q(categories__title__icontains=search_query)
                        )
                    )
                    .prefetch_related("categories")
                    .all()
                )
        return Post.objects.filter(is_displayed=True
        ).order_by("-created_at"
        ).prefetch_related("categories"
        ).all()[::-1]
        

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["Category"] = Category.objects.all()
        context['descry'] = Post.objects.filter(is_displayed=False).all()

        return context


class MyPostListView(LoginRequiredMixin, ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    redirect_field_name = "redirect_to"

    def get_queryset(self):
        return Post.objects.filter(author=self.request.user).order_by('-created_at').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['descry'] = Post.objects.filter(is_displayed=False).all()
        context['my_post'] = True
        return context


class PostView(DetailView):
    model = Post
    template_name = "blog/post.html"
    context_object_name = "post"

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data()
        context["comments"] = (
            Comment.objects.filter(post=self.kwargs["pk"]).order_by("-created_at").all()
        )
        context['descry'] = Post.objects.filter(is_displayed=False).all()
        return context


@login_required
def create_comment(request):
    if request.is_ajax():
        content = request.POST.get("content")
        post_id = int(request.POST.get("post_id"))
        post = Post.objects.filter(pk=post_id).first()
        comment = Comment(comment=content, author=request.user, post=post)
        comment.save()
        return JsonResponse({"success": True})


@login_required
def change_post(request, post_id):
    if request.method == "GET":
        return _change_post_get(request, post_id)
    post = Post.objects.get(id=post_id)
    if post.author != request.user and not request.user.is_staff:
        return redirect(reverse_lazy("blog_home"))

    form = PostForm(request.POST, request.FILES)
    form.instance.author = post.author
    if form.is_valid():
        new_post = form.save()
        if not request.FILES:
            new_post.image = post.image
        post.delete()
        if request.user.is_staff:
            new_post.is_displayed = True
            new_post.created_at = post.created_at
        new_post.save()
    return redirect(reverse_lazy("blog_home"))


def _change_post_get(request, post_id):
    post = Post.objects.get(id=post_id)
    if post.author != request.user and not request.user.is_staff:
        return redirect(reverse_lazy("blog_home"))
    form = PostForm()
    for k, v in form.fields.items():
        for i in list(post._meta.fields):
            if k == i.name:
                form.fields[k].initial = getattr(post, i.name)
                break
    return render(request, "blog/post_create.html", {"form": form})
