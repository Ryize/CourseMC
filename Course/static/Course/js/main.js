document.addEventListener('DOMContentLoaded', function () {
	if (document.location.pathname == '/') {
		document.body.classList.add('main');
		document.querySelector('#headerRight').classList.remove('black');
	}
	if (localStorage.getItem('theme')) {
		document.body.classList.add("black");
	}
	const targetModal = document.querySelectorAll('*[data-modal-target]');
const body = document.body;
for (let i = 0; i < targetModal.length; i++) { 
	targetModal[i].addEventListener('click', function () {
		let modalID = targetModal[i].getAttribute('data-modal-target');
		openModal(modalID);
	});
}
function openModal(modalID) {
	let modal = document.getElementById(modalID);
	let modalClose = modal.querySelectorAll('*[data-modal-close]');

	modal.setAttribute('aria-hidden', 'false');
	modal.classList.add('show');
	modal.querySelector('.modal-backdrop').classList.add('show');

	body.style.cssText = `overflow:hidden;`

	for (let i = 0; i < modalClose.length; i++) {
		modalClose[i].addEventListener('click', function () {
			modal.setAttribute('aria-hidden', 'true');
			modal.addEventListener('animationend', function () {
				modal.classList.remove('show');
				modal.querySelector('.modal-backdrop').classList.remove('show');
				body.style.cssText = ``
			}, { once: true });
		});
	}
}
});
const menu = document.querySelector(".menu");
const navigation = document.querySelector(".navigation");
const dropdown = document.querySelectorAll("#dropdown");
const dropdownSchedule = document.querySelectorAll("#dropdownSchedule");
const drop = document.querySelectorAll(".drop");
const dropitemMenu = document.querySelectorAll(".navigation .action");
const dropMenu = document.querySelectorAll(".navigation ul ul");
const header = document.querySelector("#headerRight");
const scheduleList = document.querySelector(".list");
const filterDropdown = document.querySelector(".dropdown-filter");
const filter = document.querySelector(".filter");
const filterItems = filterDropdown?.querySelectorAll("div");
const paginationNumbers = document.getElementById("pagination-numbers");
const paginationContainer = document.querySelector(".pagination-container");
const listItems = document.querySelectorAll("#dropdown");
const back = document.querySelector(".back");
const next = document.querySelector(".next");
 
let paginationLimit = 20;
const pageCount = Math.ceil(listItems.length / paginationLimit);
let currentPage = 1;
let doit;
function refreshScrollTrigger() {
	ScrollTrigger.refresh();
}

function activeDropDown(num) {
	dropdown[num].classList.toggle("active");
	clearTimeout(doit);
	doit = setTimeout(refreshScrollTrigger, 500);
}

header.addEventListener("click", (e) => {
	e.stopPropagation();
});

filter?.addEventListener("click", (e) => {
	e.stopPropagation();
});

setTimeout(() => {
	drop[0].style.transition = "0.5s";
	drop[1].style.transition = "0.5s";
	drop[2].style.transition = "0.5s";
}, 1000);

function activeDropDownNav(num) {
	drop[num].classList.toggle("active");
	if (num == 0) {
		drop[1].classList.remove("active");
		drop[2].classList.remove("active");
	}
	if (num == 1) {
		drop[0].classList.remove("active");
		drop[2].classList.remove("active");
	}
	if (num == 2) {
		drop[1].classList.remove("active");
		drop[0].classList.remove("active");
	}
}

function activeFilter() {
	if (filterDropdown) {
		filterDropdown.classList.toggle("active");
	}
	if (filter) {
		filter.classList.toggle("active");
	}
}

function activeFilterItem(num) {
	filterItems[num].classList.toggle("active");
	if (filterDropdown) {
		filterDropdown.classList.toggle("active");
	}
	if (num == 0) {
		filterItems[1].classList.remove("active");
		filterItems[2].classList.remove("active");
		paginationContainer.style.display = "flex";

		paginationLimit = 20;

		let activeItems = scheduleList.querySelectorAll(".item");
		activeItems.forEach((elem) => {
			elem.style.display = "block";
		});
		setCurrentPage(1);
	}
	if (num == 1) {
		filterItems[0].classList.remove("active");
		filterItems[2].classList.remove("active");
		paginationContainer.style.display = "none";

		paginationLimit = listItems.length;

		let notActiveItems = scheduleList.querySelectorAll(".item");
		notActiveItems.forEach((elem) => {
			elem.style.display = "block";
			if (!elem.classList.contains("new")) {
				elem.style.display = "none";
			}
		});
		setCurrentPage(1);
	}
	if (num == 2) {
		filterItems[1].classList.remove("active");
		filterItems[0].classList.remove("active");
		paginationContainer.style.display = "none";

		paginationLimit = listItems.length;

		let notActiveItems = scheduleList.querySelectorAll(".item");
		notActiveItems.forEach((elem) => {
			elem.style.display = "block";
			if (!elem.classList.contains("primary")) {
				elem.style.display = "none";
			}
		});
		setCurrentPage(1);
	}
}

function closeAll() {
	drop[0].classList.remove("active");
	drop[1].classList.remove("active");
	drop[2].classList.remove("active");
	if (filterDropdown) {
		filterDropdown.classList.remove("active");
	}
	if (filter) {
		filter.classList.remove("active");

	}
}

function activeDropDownNavMob(num) {
	dropitemMenu[num].classList.toggle("active");
	dropMenu[num].classList.toggle("active");
}

menu.addEventListener("click", () => {
	menu.classList.toggle("active");
	if (navigation) {
		navigation.classList.toggle("active");
	}
});

const items = gsap.utils.toArray(["section:nth-child(4) .right img", "section:nth-child(2) img", "section:nth-child(2) .container div", "section:nth-child(4) .left", "section:nth-child(3) .left", "section:nth-child(3) .right", "section:nth-child(5) .item", "section:nth-child(6) img", "section:nth-child(6) .right", "section:nth-child(7) .container", "section:nth-child(8) .left", "section:nth-child(8) .right", "section:nth-child(9) .container", "section:nth-child(11) form label", "section:nth-child(11) form input", "section:nth-child(11) form button"]);
items.forEach((item, i) => {
	ScrollTrigger.create({
		// markers: true,
		trigger: item,
		start: "top bottom",
		toggleClass: "active"
	});
});

const appendPageNumber = (index) => {
	const pageNumber = document.createElement("button");
	pageNumber.className = "pagination-number";
	pageNumber.innerHTML = index;
	pageNumber.setAttribute("page-index", index);
	pageNumber.setAttribute("aria-label", "Page " + index);
	if (paginationNumbers) {

		paginationNumbers.appendChild(pageNumber);
	}
};

const getPaginationNumbers = () => {
	for (let i = 1; i <= pageCount; i++) {
		appendPageNumber(i);
	}
};

const handleActivePageNumber = () => {
	document.querySelectorAll(".pagination-number").forEach((button) => {
		button.classList.remove("active");
		const pageIndex = Number(button.getAttribute("page-index"));
		if (pageIndex == currentPage) {
			button.classList.add("active");
		}
	});
};

function setCurrentPage(pageNum) {
	currentPage = pageNum;
	handleActivePageNumber();

	const prevRange = (pageNum - 1) * paginationLimit;
	const currRange = pageNum * paginationLimit;

	listItems.forEach((item, index) => {
		item.classList.add("hidden");
		if (index >= prevRange && index < currRange) {
			item.classList.remove("hidden");
		}
	});
}
if (back) {
	back.addEventListener("click", () => {
		if (currentPage > 1) {
			setCurrentPage(currentPage - 1);
		}
	});
}

if (next) {
	next.addEventListener("click", () => {
		if (currentPage < pageCount) {
			setCurrentPage(currentPage + 1);
		}
	});
}

window.addEventListener("load", () => {
	getPaginationNumbers();
	setCurrentPage(1);

	document.querySelectorAll(".pagination-number").forEach((button) => {
		const pageIndex = Number(button.getAttribute("page-index"));

		if (pageIndex) {
			button.addEventListener("click", () => {
				setCurrentPage(pageIndex);
			});
		}
	});

	if (pageCount >= 10) {
		paginationContainer.classList.add("grid");
	}
});

function changeTheme() {
	document.body.classList.toggle("black");
	if (!localStorage.getItem('theme')) {
		localStorage.setItem('theme', 'dark');
	}
	else {
		localStorage.setItem('theme', '');
	}
}
