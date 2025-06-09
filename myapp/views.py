from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from .models import Image, Advertisement, Comment
from .forms import ImageForm, AdvertisementForm
from django.contrib.auth.decorators import login_required

from django.shortcuts import render
from .models import Image 


# Home view (blog list)
def home(request):
    images = Image.objects.all().order_by('-created_at')
    advertisements = Advertisement.objects.filter(status='enable').order_by('order')
    form = ImageForm()
    search_query = request.GET.get('q', '')
    
    if search_query:
        images = images.filter(
            Q(heading__icontains=search_query) | 
            Q(description__icontains=search_query)
        )

    if request.method == 'POST':
        form = ImageForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('home')

    return render(request, 'puja/home.html', {
        'images': images,
        'advertisements': advertisements,
        'form': form,
        'search_query': search_query
    })

# Blog detail view
def blog_detail(request, image_id):
    image = get_object_or_404(Image, id=image_id)
    comments = image.comments.filter(parent__isnull=True)  # Get top-level comments

    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        website = request.POST.get('website', '')
        comment_text = request.POST.get('comment')
        parent_id = request.POST.get('parent_id')  # For replies

        if name and email and comment_text:
            comment = Comment(
                image=image,
                name=name,
                email=email,
                website=website if website else None,
                comment=comment_text,
                parent=Comment.objects.get(id=parent_id) if parent_id else None
            )
            comment.save()
            return redirect('myapp:blog_detail', image_id=image_id)

    return render(request, 'puja/blog-details.html', {
        'image': image,
        'comments': comments
    })

@login_required(login_url='/')
def advertisement(request):
    form = AdvertisementForm()

    # Handle POST request for adding an advertisement
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('advertisement')

    # Render advertisement template with the form
    return render(request, 'advertisements/adverhome.html', {'form': form})
