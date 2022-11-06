from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
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


class PostListView(ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"

    def get_queryset(self):
        if self.request.GET:
            try:
                search_query = self.request.GET.get('search')
                return (
                    Post.objects.filter(Q(is_displayed=True) &
                                        (Q(title__icontains=search_query) | Q(description__icontains=search_query))
                                        )
                    .order_by("-created_at")
                    .prefetch_related("categories")
                    .all()
                )
            except ValueError:
                pass
        return (
            Post.objects.filter(is_displayed=True)
            .order_by("-created_at")
            .prefetch_related("categories")
            .all()
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["Category"] = Category.objects.all()

        return context


class MyPostListView(LoginRequiredMixin, ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    redirect_field_name = "redirect_to"

    def get_queryset(self):
        return Post.objects.filter(author=self.request.user).all()


class PostView(DetailView):
    model = Post
    template_name = "blog/post.html"
    context_object_name = "post"

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data()
        context["comments"] = (
            Comment.objects.filter(post=self.kwargs["pk"]).order_by("-created_at").all()
        )
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
