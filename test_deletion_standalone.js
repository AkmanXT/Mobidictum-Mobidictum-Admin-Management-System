const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false }); // Show browser for debugging
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {
    // Load auth state if available
    const fs = require('fs');
    const authStatePath = 'auth/state.json';
    if (fs.existsSync(authStatePath)) {
      const authState = JSON.parse(fs.readFileSync(authStatePath, 'utf8'));
      await context.addCookies(authState.cookies || []);
    }
    
    // Use the NEW URL from the fresh scrape (246979)
    const editUrl = 'https://fienta.com/my/events/118714/discounts/246979/edit';
    console.log('🌐 Navigating to:', editUrl);
    await page.goto(editUrl);
    await page.waitForLoadState('networkidle');
    
    // Take a screenshot to see what we're dealing with
    await page.screenshot({ path: 'before_deletion.png', fullPage: true });
    console.log('📸 Screenshot saved: before_deletion.png');
    
    // Look for the specific Delete button with class btn-delete
    console.log('🔍 Looking for Delete button with class .btn-delete...');
    
    // Debug: List all buttons on the page first
    const allButtons = await page.locator('button').all();
    console.log('📋 Available buttons on page:');
    for (const btn of allButtons) {
      const text = await btn.textContent();
      const className = await btn.getAttribute('class');
      console.log(`  Button: "${text}" class: "${className}"`);
    }
    
    // Try multiple selectors for the delete button
    const deleteSelectors = [
      'button.btn-delete',
      '.btn-delete',
      'button:has-text("Delete")',
      'input[value="Delete"]',
      'button[type="button"]:has-text("Delete")',
      '.btn.btn-delete',
      '.btn-default.btn-delete'
    ];
    
    let deleteButton = null;
    let usedSelector = '';
    
    for (const selector of deleteSelectors) {
      try {
        const btn = page.locator(selector);
        if (await btn.isVisible({ timeout: 2000 })) {
          deleteButton = btn;
          usedSelector = selector;
          console.log(`✅ Found Delete button using selector: ${selector}`);
          break;
        }
      } catch (e) {
        // Continue to next selector
      }
    }
    
    if (deleteButton) {
      console.log('🖱️ Clicking Delete button...');
      await deleteButton.click();
      
      // Wait a moment and take another screenshot
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'after_click.png', fullPage: true });
      console.log('📸 Screenshot after click: after_click.png');
      
      // Handle any confirmation dialog (could be modal or alert)
      try {
        console.log('⏳ Waiting for confirmation dialog...');
        await page.waitForTimeout(1000); // Give time for modal to appear
        
        // Look for common confirmation patterns
        const confirmSelectors = [
          'button:has-text("Confirm")',
          'button:has-text("Yes")', 
          'button:has-text("Delete")',
          'button:has-text("OK")',
          '.btn-danger:has-text("Delete")',
          '.btn-primary:has-text("Confirm")',
          '[data-dismiss="modal"]:has-text("Delete")',
          '.modal button:has-text("Delete")',
          '.modal button:has-text("Yes")'
        ];
        
        let confirmed = false;
        for (const selector of confirmSelectors) {
          try {
            const confirmButton = page.locator(selector);
            if (await confirmButton.isVisible({ timeout: 2000 })) {
              console.log(`✅ Found confirmation button: ${selector}`);
              await confirmButton.click();
              confirmed = true;
              console.log('✅ Clicked confirmation button');
              break;
            }
          } catch (e) {
            // Continue to next selector
          }
        }
        
        if (!confirmed) {
          console.log('ℹ️ No confirmation dialog found or already confirmed');
        }
        
      } catch (e) {
        console.log('ℹ️ No confirmation dialog needed or error:', e.message);
      }
      
      // Wait for operation to complete
      console.log('⏳ Waiting for operation to complete...');
      await page.waitForTimeout(3000);
      
      // Take final screenshot
      await page.screenshot({ path: 'final_result.png', fullPage: true });
      console.log('📸 Final screenshot: final_result.png');
      
      // Check if we're redirected to discounts list (indicates success)
      const currentUrl = page.url();
      console.log('🌐 Current URL:', currentUrl);
      
      if (currentUrl.includes('/discounts') && !currentUrl.includes('/edit')) {
        console.log('✅ SUCCESS: Redirected to discounts list - deletion likely successful!');
        process.exit(0);
      } else if (currentUrl.includes('404') || currentUrl.includes('not-found')) {
        console.log('✅ SUCCESS: Page not found - code was deleted!');
        process.exit(0);
      } else {
        console.log('⚠️ UNCLEAR: Still on edit page or unexpected URL');
        console.log('Check the screenshots to see what happened');
        process.exit(0);
      }
      
    } else {
      console.error('❌ FAILED: Delete button not found with any selector');
      
      // Take screenshot of what we see
      await page.screenshot({ path: 'no_delete_button.png', fullPage: true });
      console.log('📸 Screenshot saved: no_delete_button.png');
      
      process.exit(1);
    }
    
  } catch (error) {
    console.error('❌ ERROR:', error.message);
    
    // Take error screenshot
    await page.screenshot({ path: 'error.png', fullPage: true }).catch(() => {});
    console.log('📸 Error screenshot: error.png');
    
    console.error('Stack:', error.stack);
    process.exit(1);
  } finally {
    console.log('🔚 Closing browser...');
    await browser.close();
  }
})();
