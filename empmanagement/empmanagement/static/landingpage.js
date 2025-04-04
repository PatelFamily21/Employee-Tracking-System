// Initialize all interactive elements when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  // Initialize all components
  initMobileMenu();
  initSmoothScrolling();
  initContactForm();
  initNavbarScroll();
  initAnimations();
});

// Mobile menu functionality
function initMobileMenu() {
  const mobileMenuButton = document.getElementById('mobile-menu-button');
  const mobileMenu = document.getElementById('mobile-menu');

  if (mobileMenuButton && mobileMenu) {
    mobileMenuButton.addEventListener('click', () => {
      mobileMenu.classList.toggle('active');
      mobileMenu.classList.toggle('-translate-x-full');
    });

    // Close mobile menu when clicking on a link
    const mobileMenuLinks = mobileMenu.querySelectorAll('a');
    mobileMenuLinks.forEach(link => {
      link.addEventListener('click', () => {
        mobileMenu.classList.remove('active');
        mobileMenu.classList.add('-translate-x-full');
      });
    });
  }
}

// Smooth scrolling for anchor links
function initSmoothScrolling() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      
      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        window.scrollTo({
          top: targetElement.offsetTop,
          behavior: 'smooth'
        });
      }
    });
  });
}

// Contact form validation
function initContactForm() {
  const contactForm = document.getElementById('contact-form');
  
  if (contactForm) {
    const nameInput = document.getElementById('name');
    const emailInput = document.getElementById('email');
    const messageInput = document.getElementById('message');
    const nameError = document.getElementById('name-error');
    const emailError = document.getElementById('email-error');
    const messageError = document.getElementById('message-error');

    contactForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      // Reset errors
      nameError.classList.add('hidden');
      emailError.classList.add('hidden');
      messageError.classList.add('hidden');
      
      let isValid = true;
      
      // Validate name
      if (!nameInput.value.trim()) {
        nameError.textContent = 'Name is required';
        nameError.classList.remove('hidden');
        isValid = false;
      }
      
      // Validate email
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailInput.value.trim()) {
        emailError.textContent = 'Email is required';
        emailError.classList.remove('hidden');
        isValid = false;
      } else if (!emailRegex.test(emailInput.value.trim())) {
        emailError.textContent = 'Please enter a valid email address';
        emailError.classList.remove('hidden');
        isValid = false;
      }
      
      // Validate message
      if (!messageInput.value.trim()) {
        messageError.textContent = 'Message is required';
        messageError.classList.remove('hidden');
        isValid = false;
      }
      
      // If valid, submit the form (or show success message in this case)
      if (isValid) {
        // In a real application, you would submit the form to a server
        // Here we're just showing a success message
        contactForm.innerHTML = `
          <div class="text-center py-6">
            <div class="text-green-500 mb-4">
              <i class="fa-solid fa-circle-check text-5xl"></i>
            </div>
            <h3 class="text-xl font-medium text-gray-900 mb-2">Thank you for your message!</h3>
            <p class="text-gray-600">We'll get back to you as soon as possible.</p>
          </div>
        `;
      }
    });
  }
}

// Navbar scroll behavior (change background color on scroll)
function initNavbarScroll() {
  const navbar = document.querySelector('nav');
  
  if (navbar) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 50) {
        navbar.classList.add('bg-white', 'shadow-md');
        navbar.classList.remove('bg-transparent');
      } else {
        navbar.classList.remove('bg-white', 'shadow-md');
        navbar.classList.add('bg-transparent');
      }
    });
  }
}

// Simple animations for feature cards
function initAnimations() {
  const featureCards = document.querySelectorAll('.feature-card');
  
  featureCards.forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.classList.add('transform', 'scale-105', 'shadow-md');
    });
    
    card.addEventListener('mouseleave', () => {
      card.classList.remove('transform', 'scale-105', 'shadow-md');
    });
  });
}