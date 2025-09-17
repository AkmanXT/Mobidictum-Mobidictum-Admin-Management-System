/**
 * Fresh Fienta Login Script
 * Runs on server to authenticate and save session state
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function loginToFienta() {
    console.log('🔐 Starting fresh Fienta login...');
    
    const browser = await chromium.launch({ 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        
        // Navigate to Fienta login
        console.log('📱 Navigating to Fienta login...');
        await page.goto('https://fienta.com/auth/login');
        
        // Wait for login form
        await page.waitForSelector('input[type="email"]', { timeout: 10000 });
        
        // Fill credentials
        const email = process.env.FIENTA_EMAIL;
        const password = process.env.FIENTA_PASSWORD;
        
        if (!email || !password) {
            throw new Error('FIENTA_EMAIL and FIENTA_PASSWORD environment variables required');
        }
        
        console.log(`📧 Logging in as: ${email}`);
        await page.fill('input[type="email"]', email);
        await page.fill('input[type="password"]', password);
        
        // Submit login
        await page.click('button[type="submit"], .btn-primary, [data-testid="login-button"]');
        
        // Wait for redirect to dashboard
        console.log('⏳ Waiting for successful login...');
        await page.waitForURL(/fienta\.com\/my/, { timeout: 30000 });
        
        // Navigate to discounts to ensure we're in the right place
        console.log('🎫 Navigating to discount codes...');
        await page.goto(`https://fienta.com/my/events/${process.env.FIENTA_EVENT_ID || '118714'}/discounts`);
        
        // Wait for discounts page to load
        await page.waitForSelector('.discount-list, .codes-table, [data-testid="discount-codes"]', { 
            timeout: 15000 
        });
        
        // Save authentication state
        console.log('💾 Saving authentication state...');
        const authDir = path.join(process.cwd(), 'auth');
        if (!fs.existsSync(authDir)) {
            fs.mkdirSync(authDir, { recursive: true });
        }
        
        const state = await context.storageState();
        fs.writeFileSync(path.join(authDir, 'state.json'), JSON.stringify(state, null, 2));
        
        console.log('✅ Login successful! Authentication state saved.');
        console.log(`🍪 Saved ${state.cookies.length} cookies`);
        console.log(`🌐 Saved ${state.origins.length} origins`);
        
        return {
            success: true,
            message: 'Login successful',
            cookies: state.cookies.length,
            origins: state.origins.length
        };
        
    } catch (error) {
        console.error('❌ Login failed:', error.message);
        
        // Take screenshot for debugging
        try {
            const page = context.pages()[0];
            if (page) {
                await page.screenshot({ 
                    path: 'logs/login_error.png',
                    fullPage: true 
                });
                console.log('📸 Screenshot saved to logs/login_error.png');
            }
        } catch (screenshotError) {
            console.error('Failed to take screenshot:', screenshotError.message);
        }
        
        throw error;
        
    } finally {
        await browser.close();
    }
}

// Run if called directly
if (require.main === module) {
    loginToFienta()
        .then(result => {
            console.log('🎉 Result:', result);
            process.exit(0);
        })
        .catch(error => {
            console.error('💥 Fatal error:', error);
            process.exit(1);
        });
}

module.exports = { loginToFienta };
