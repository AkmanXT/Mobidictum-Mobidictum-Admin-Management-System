
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
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
    
    const eventId = '118714';
    let targetUrl = 'https://fienta.com/my/events/118714/discounts/247420/edit';
    if (!targetUrl || targetUrl === 'null') {
      // Fallback: open discounts list and find the code by text
      const listUrl = `https://fienta.com/my/events/${eventId}/discounts`;
      console.log('Navigating to list:', listUrl);
      await page.goto(listUrl);
      await page.waitForLoadState('networkidle');
      // Try to find the row link with code text
      const codeText = 'SERAKM-002-MFKIJ4QCUQ6';
      const link = page.locator(`a:has-text("${codeText}")`).first();
      await link.waitFor({ timeout: 10000 });
      const href = await link.getAttribute('href');
      if (!href) {
        console.error('Could not find edit link for code in list');
        process.exit(1);
      }
      targetUrl = href.startsWith('http') ? href : `https://fienta.com${href}`;
    }
    console.log('Navigating to:', targetUrl);
    await page.goto(targetUrl);
    await page.waitForLoadState('networkidle');
    
    // Look for the specific Delete button with class btn-delete
    console.log('Looking for Delete button with class .btn-delete...');
    const deleteButton = page.locator('button.btn-delete, .btn-delete');
    
    // Wait for the button to be visible
    await deleteButton.waitFor({ state: 'visible', timeout: 10000 });
    
    if (await deleteButton.isVisible()) {
      console.log('Found Delete button! Clicking...');
      await deleteButton.click();
      
      // Handle any confirmation dialog (could be modal or alert)
      try {
        // Wait for confirmation modal/dialog
        console.log('Waiting for confirmation dialog...');
        await page.waitForTimeout(1000); // Give time for modal to appear
        
        // Look for common confirmation patterns
        const confirmSelectors = [
          'button:has-text("Confirm")',
          'button:has-text("Yes")', 
          'button:has-text("Delete")',
          'button:has-text("OK")',
          '.btn-danger:has-text("Delete")',
          '.btn-primary:has-text("Confirm")',
          '[data-dismiss="modal"]:has-text("Delete")'
        ];
        
        let confirmed = false;
        for (const selector of confirmSelectors) {
          try {
            const confirmButton = page.locator(selector);
            if (await confirmButton.isVisible({ timeout: 2000 })) {
              console.log(`Found confirmation button: ${selector}`);
              await confirmButton.click();
              confirmed = true;
              break;
            }
          } catch (e) {
            // Continue to next selector
          }
        }
        
        if (!confirmed) {
          console.log('No confirmation dialog found or already confirmed');
        }
        
      } catch (e) {
        console.log('No confirmation dialog needed or error:', e.message);
      }
      
      // Wait for navigation or success indicator
      console.log('Waiting for operation to complete...');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      
      // Check if we're redirected to discounts list
      const currentUrl = page.url();
      if (currentUrl.includes('/discounts') && !currentUrl.includes('/edit')) {
        console.log('Redirected to discounts list - verifying code deletion...');
        
        // Verify the code is actually deleted by checking if it still exists
        try {
          // Search for the code in the current page
          const codeRows = await page.locator('tbody tr').all();
          let codeFound = false;
          
          for (const row of codeRows) {
            try {
              const codeButton = row.locator('button[data-code]');
              const codeText = await codeButton.getAttribute('data-code');
              if (codeText === 'SERAKM-002-MFKIJ4QCUQ6') {
                codeFound = true;
                break;
              }
            } catch (e) {
              // Continue checking other rows
            }
          }
          
          if (codeFound) {
            console.log('❌ Code SERAKM-002-MFKIJ4QCUQ6 still found on page - deletion failed');
            process.exit(1);
          } else {
            console.log('✅ Code SERAKM-002-MFKIJ4QCUQ6 successfully deleted - not found on discounts page');
            process.exit(0);
          }
          
        } catch (e) {
          console.log('❌ Error verifying deletion:', e.message);
          process.exit(1);
        }
        
      } else {
        console.log('❌ Still on edit page after attempting delete. URL:', currentUrl);
        process.exit(1);
      }
      
    } else {
      console.error('❌ Delete button with class .btn-delete not found');
      
      // Debug: List all buttons on the page
      const allButtons = await page.locator('button').all();
      console.log('Available buttons on page:');
      for (const btn of allButtons) {
        const text = await btn.textContent();
        const className = await btn.getAttribute('class');
        console.log(`  Button: "${text}" class: "${className}"`);
      }
      
      process.exit(1);
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    console.error('Stack:', error.stack);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
