var matchHeight = function () {
    var div = '';

    function init(div) {
        eventListeners();
        matchHeight(div);
    }

    function eventListeners() {
        $(window).on('resize', function () {
            matchHeight();
        });
    }

    function matchHeight(div) {
        var groupName = $(div);
        var groupHeights = [];
        groupName.css('min-height', 'auto');
        groupName.each(function () {
            groupHeights.push($(this).outerHeight());
        });
        var maxHeight = Math.max.apply(null, groupHeights);
        groupName.css('min-height', maxHeight);
    };
    return {
        init: init
    };
}();

jQuery(document).ready(function ($) {

    if ($(window).width() >= 767.99) {
        matchHeight.init('#guarantees .col-md-3 > .img');
        matchHeight.init('#guarantees .col-md-3 > .text');
    }


    var scrollPrev = 0;
    $(window).scroll(function () {
        var scrolled = $(window).scrollTop();
        var checkpoint = 71;
        var $header = $('.fixed-top');
        if (scrolled < scrollPrev) {
            if (scrolled > checkpoint) {
                $header.addClass('fixed-active');
                setTimeout(function () {
                    $header
                }, 200);
            } else {
                $header.removeClass('fixed-active');
            }
        } else {
            $header.removeClass('fixed-active');
            if (scrolled > checkpoint) {
                $header.addClass('fixed-active')
            }
        }
        scrollPrev = scrolled;
    });
    var scrolled = $(window).scrollTop();
    var checkpoint = 71;
    var $header = $('.fixed-top');
    if (scrolled < scrollPrev) {
        if (scrolled > checkpoint) {
            $header.addClass('fixed-active');
            setTimeout(function () {
                $header
            }, 200);
        } else {
            $header.removeClass('fixed-active');
        }
    } else {
        $header.removeClass('fixed-active');
        if (scrolled > checkpoint) {
            $header.addClass('fixed-active')
        }
    }
    scrollPrev = scrolled;

    $(".tools-tabs li a").click(function (e) {
        e.preventDefault();
        $(".tools-tabs li").removeClass("active");
        $(this).closest('li').addClass("active");
        $(".tab_content_container > .tab_content_active").removeClass("tab_content_active");
        $(this.rel).addClass("tab_content_active");
    });
});

jQuery('img.svg').each(function () {
    var $img = jQuery(this);
    var imgID = $img.attr('id');
    var imgClass = $img.attr('class');
    var imgURL = $img.attr('src');

    jQuery.get(imgURL, function (data) {
        var $svg = jQuery(data).find('svg');

        if (typeof imgID !== 'undefined') {
            $svg = $svg.attr('id', imgID);
        }
        if (typeof imgClass !== 'undefined') {
            $svg = $svg.attr('class', imgClass + ' replaced-svg');
        }

        $svg = $svg.removeAttr('xmlns:a');

        if (!$svg.attr('viewBox') && $svg.attr('height') && $svg.attr('width')) {
            $svg.attr('viewBox', '0 0 ' + $svg.attr('height') + ' ' + $svg.attr('width'))
        }

        $img.replaceWith($svg);

    }, 'xml');

});

if (document.querySelector(".courses-menu")) {
    const coursesMenu = document.querySelector(".courses-menu");
    const showMenuBtn = document.querySelector(".show-courses-menu");
    const closeBtn = document.querySelector(".courses-menu__close-btn");

    
    showMenuBtn && showMenuBtn.addEventListener("click", (e) => {
        e.preventDefault()
        coursesMenu.classList.add("courses-menu--show")
    });

    closeBtn.addEventListener("click", () => coursesMenu.classList.remove("courses-menu--show"));

    const trendList = document.querySelector(".trends ul");
    const courses = document.getElementsByClassName("courses__items");
    const trends = document.getElementsByClassName("trend");

    trendList.addEventListener("mouseover", (event) => {
        const target = event.target;
        const courseURL = target.getAttribute("data-tab");
        if (courseURL) {
            const courseItem = document.getElementById(courseURL);
            const onlineItem = document.getElementById('online_' + courseURL);

            for (let trend of trends) {
                trend.classList.remove("trend--active");
            }

            target.classList.add("trend--active");

            for (let course of courses) {
                course.classList.remove("courses__items--show");
            }
            courseItem.classList.toggle("courses__items--show");
            onlineItem.classList.toggle("courses__items--show");
        }
    });
}

$('.teacher-portfolio_item').on('click', function(e) { 
    e.preventDefault();
    const dataAttr = e.target.parentElement.getAttribute("data-teach-fancybox");
    const teacherPortfolios = document.querySelectorAll(`.slick-active [data-teach-fancybox="${dataAttr}"]`);
    let index = 0;
    for (teacherPortfolio of teacherPortfolios) {
        teacherPortfolio.setAttribute("index", index)
        index++;
    }
    $.fancybox.open(teacherPortfolios, {}, +e.target.parentElement.getAttribute("index"));
});

function copyToClipboard(element) {
  var $temp = $("<input>");
  $("body").append($temp);
  $temp.val($(element).text()).select();
  document.execCommand("copy");
  $temp.remove();
}