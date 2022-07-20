;(function() {

	// коллекция всех элементов на странице, которые могут открывать всплывающие окна
	// их отличительной особенность является наличие атрибута '[data-modal]'
	const mOpen = document.querySelectorAll('[data-modal]');
	// если нет элементов управления всплывающими окнами, прекращаем работу скрипта
	if (mOpen.length == 0) return;

		  // подложка под всплывающее окно
	const overlay = document.querySelector('.overlay'),
		  // коллекция всплывающих окон
		  modals = document.querySelectorAll('.dlg-modal'),
		  // коллекция всех элементов на странице, которые могут
		  // закрывать всплывающие окна
		  // их отличительной особенность является наличие атрибута '[data-close]'
		  mClose = document.querySelectorAll('[data-close]');
	// флаг всплывающего окна: false - окно закрыто, true - открыто
	let	mStatus = false;

	for (let el of mOpen) {
		el.addEventListener('click', function(e) {
			// используюя атрибут [data-modal], определяем ID всплывающего окна,
			// которое требуется открыть
			// по значению ID получаем ссылку на элемент с таким идентификатором
			let modalId = el.dataset.modal,
				modal = document.getElementById(modalId);
			// вызываем функцию открытия всплывающего окна, аргументом
			// является объект всплывающего окна
			modalShow(modal);
		});
	}

	// регистрируются обработчики событий на элементах, закрывающих
	// всплывающие окна
	for (let el of mClose) {
		el.addEventListener('click', modalClose);
	}

	// регистрируются обработчик события нажатия на клавишу
	document.addEventListener('keydown', modalClose);

	function modalShow(modal) {
		// показываем подложку всплывающего окна
		overlay.classList.remove('fadeOut');
		overlay.classList.add('fadeIn');

		// определяем тип анимации появления всплывающего окна
		// убираем и добавляем классы, соответствующие типу анимации
		if (typeAnimate === 'fade') {
			modal.classList.remove('fadeOut');
			modal.classList.add('fadeIn');
		} else if (typeAnimate === 'slide') {
			modal.classList.remove('slideOutUp');
			modal.classList.add('slideInDown');
		}
		// выставляем флаг, обозначающий, что всплывающее окно открыто
		mStatus = true;
	}

	function modalClose(event) {
		if (mStatus && ( event.type != 'keydown' || event.keyCode === 27 ) ) {
			// обходим по очереди каждый элемент коллекции modals (каждое всплывающее окно)
			// и в зависимости от типа анимации, используемой на данной странице,
			// удаляем класс анимации открытия окна и добавляем класс анимации закрытия
			for (let modal of modals) {
				if (typeAnimate == 'fade') {
					modal.classList.remove('fadeIn');
					modal.classList.add('fadeOut');
				} else if (typeAnimate == 'slide') {
					modal.classList.remove('slideInDown');
					modal.classList.add('slideOutUp');
				}
			}

			// закрываем overlay
			overlay.classList.remove('fadeIn');
			overlay.classList.add('fadeOut');
			// сбрасываем флаг, устанавливая его значение в 'false'
			// это значение указывает нам, что на странице нет открытых
			// всплывающих окон
			mStatus = false;
		}
	}
})();
