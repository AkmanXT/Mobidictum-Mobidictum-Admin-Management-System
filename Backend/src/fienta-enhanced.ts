import { Page } from 'playwright';
import { logger } from './logger';

export interface CodeUsageData {
  code: string;
  ordersUsed: number;
  orderLimit: number;
  ticketsUsed: number;
  ticketLimit: number;
  orders: OrderInfo[];
  discountId?: string | null;
  editUrl?: string;
}

export interface OrderInfo {
  orderId: string;
  orderDate: string;
  customerEmail: string;
  customerName?: string;
  customerPhone?: string;
  ticketCount: number;
  totalAmount: string;
  currency: string;
  status: string;
  discountCode?: string;
  ticketDetails: TicketInfo[];
}

export interface TicketInfo {
  ticketCode: string;
  ticketType: string;
  attendeeEmail: string;
  attendeeName?: string;
  price: string;
}

export interface CodeDetails {
  code: string;
  discount: string;
  discountType: 'percentage' | 'amount';
  orderLimit: number;
  ticketLimit: number;
  ordersUsed: number;
  ticketsUsed: number;
  validFrom?: string;
  validTo?: string;
  ticketTypes: string[];
  description?: string;
  isTemporarilyDisabled: boolean;
}

export class FientaEnhancedScraper {
  constructor(private page: Page, private baseUrl: string = 'https://fienta.com') {}

  /**
   * Get comprehensive usage data for a discount code
   */
  async getCodeUsageData(eventId: string, code: string): Promise<CodeUsageData | null> {
    try {
      // First, get the code details from the discounts page
      const discountsUrl = `${this.baseUrl}/my/events/${eventId}/discounts`;
      await this.page.goto(`${discountsUrl}?search=${encodeURIComponent(code)}`);
      await this.page.waitForLoadState('networkidle');

      // Find the row containing this code
      const codeRow = this.page.locator(`tr:has(button[data-code="${code}"])`).first();
      if (!(await codeRow.count())) {
        logger.warn({ code }, 'Code not found in discounts list');
        return null;
      }

      // Extract usage info from the row (e.g., "2 / 5 orders • 3 / 10 tickets")
      const usageText = await codeRow.locator('td:nth-child(3)').textContent() || '';
      const usageMatch = usageText.match(/(\d+)\s*\/\s*(\d+)\s*orders.*?(\d+)\s*\/\s*(\d+)\s*tickets/);
      
      let ordersUsed = 0, orderLimit = 0, ticketsUsed = 0, ticketLimit = 0;
      if (usageMatch) {
        ordersUsed = parseInt(usageMatch[1]);
        orderLimit = parseInt(usageMatch[2]);
        ticketsUsed = parseInt(usageMatch[3]);
        ticketLimit = parseInt(usageMatch[4]);
      }

      // Get the discount code ID from the edit link
      const editLink = codeRow.locator('a[href*="/discounts/"][href*="/edit"]').first();
      const href = await editLink.getAttribute('href') || '';
      const discountIdMatch = href.match(/\/discounts\/(\d+)\/edit/);
      const discountId = discountIdMatch ? discountIdMatch[1] : null;

      // If code is used, get order details
      const orders: OrderInfo[] = [];
      if (ordersUsed > 0 && discountId) {
        // Navigate to orders filtered by this discount code
        const ordersUrl = `${this.baseUrl}/my/events/${eventId}/orders?discount=${discountId}`;
        await this.page.goto(ordersUrl);
        await this.page.waitForLoadState('networkidle');

        // Scrape all orders that used this code
        const orderRows = await this.page.locator('tbody tr').all();
        
        for (const row of orderRows) {
          try {
            // Extract order ID from link
            const orderLink = row.locator('a[href*="/orders/"][href*="/edit"]').first();
            const orderHref = await orderLink.getAttribute('href') || '';
            const orderIdMatch = orderHref.match(/\/orders\/(\d+)\/edit/);
            const orderId = orderIdMatch ? orderIdMatch[1] : '';

            if (!orderId) continue;

            // Get basic order info from the list
            const dateText = await row.locator('td:nth-child(2)').textContent() || '';
            const contactInfo = await row.locator('td:nth-child(3)').textContent() || '';
            const ticketCount = parseInt(await row.locator('td:nth-child(4)').textContent() || '0');
            const priceStatus = await row.locator('td:nth-child(5)').textContent() || '';

            // Extract email and phone from contact info
            const emailMatch = contactInfo.match(/([^\s]+@[^\s]+)/);
            const phoneMatch = contactInfo.match(/(\+\d+)/);
            const customerEmail = emailMatch ? emailMatch[1].trim() : '';
            const customerPhone = phoneMatch ? phoneMatch[1].trim() : '';

            // Extract price and status
            const priceMatch = priceStatus.match(/([\d.,]+)\s*([€$£])/);
            const totalAmount = priceMatch ? priceMatch[1] : '';
            const currency = priceMatch ? priceMatch[2] : '€';
            const status = priceStatus.includes('Completed') ? 'completed' : 'pending';

            // Get detailed order information
            const orderDetails = await this.getOrderDetails(orderId);

            orders.push({
              orderId,
              orderDate: dateText.trim(),
              customerEmail,
              customerPhone,
              ticketCount,
              totalAmount,
              currency,
              status,
              discountCode: code,
              ticketDetails: orderDetails?.ticketDetails || [],
              customerName: orderDetails?.customerName
            });
          } catch (err) {
            logger.error({ err, orderId: 'unknown' }, 'Failed to scrape order from list');
          }
        }
      }

      return {
        code,
        ordersUsed,
        orderLimit,
        ticketsUsed,
        ticketLimit,
        orders
      };

    } catch (err) {
      logger.error({ err, code }, 'Failed to get code usage data');
      return null;
    }
  }

  /**
   * Get detailed information about a specific order
   */
  async getOrderDetails(orderId: string): Promise<Omit<OrderInfo, 'orderId' | 'orderDate' | 'status' | 'totalAmount' | 'currency'> | null> {
    try {
      const orderUrl = `${this.baseUrl}/my/orders/${orderId}/edit`;
      await this.page.goto(orderUrl);
      await this.page.waitForLoadState('networkidle');

      // Extract customer info from the main order section
      const contactText = await this.page.locator('.card-body').first().textContent() || '';
      const emailMatch = contactText.match(/([^\s]+@[^\s]+)/);
      const phoneMatch = contactText.match(/(\+\d[\d\s]+)/);
      const customerEmail = emailMatch ? emailMatch[1].trim() : '';
      const customerPhone = phoneMatch ? phoneMatch[1].trim() : '';

      // Try to extract customer name from order details
      // This might be in various places depending on the order form
      let customerName = '';
      const nameElement = await this.page.locator('text=/Name|Nimi|İsim/i').first();
      if (await nameElement.count()) {
        const nameContainer = await nameElement.locator('..').textContent() || '';
        customerName = nameContainer.replace(/Name|Nimi|İsim/gi, '').trim();
      }

      // Extract discount code used
      const discountMatch = contactText.match(/Discount code:\s*([A-Z0-9-]+)/);
      const discountCode = discountMatch ? discountMatch[1] : undefined;

       // Extract ticket details from both .order-ticket elements and table rows
       const ticketDetails: TicketInfo[] = [];
       
       // First try to get from .order-ticket elements (main ticket display)
       const ticketElements = await this.page.locator('.order-ticket').all();
       for (const ticketEl of ticketElements) {
         try {
           // Get ticket type
           const ticketType = await ticketEl.locator('.ticket-type').textContent() || '';
           
           // Get ticket code from help block (e.g., "RN28PE92RA • 329.40 €")
           const helpText = await ticketEl.locator('.help-block').textContent() || '';
           const ticketCodeMatch = helpText.match(/([A-Z0-9]+)\s*•/);
           const ticketCode = ticketCodeMatch ? ticketCodeMatch[1] : '';
           
           // Get price
           const priceMatch = helpText.match(/([\d.,]+)\s*([€$£])/);
           const price = priceMatch ? `${priceMatch[1]} ${priceMatch[2]}` : '';

           // Get attendee email
           const attendeeInfo = await ticketEl.locator('.overflow-hidden.text-nowrap').textContent() || '';
           const attendeeEmailMatch = attendeeInfo.match(/([^\s]+@[^\s]+)/);
           const attendeeEmail = attendeeEmailMatch ? attendeeEmailMatch[1].trim() : '';

           // Try to get attendee name if available
           let attendeeName = '';
           const nameInAttendee = attendeeInfo.replace(attendeeEmail, '').trim();
           if (nameInAttendee) {
             attendeeName = nameInAttendee;
           }

           ticketDetails.push({
             ticketCode,
             ticketType: ticketType.trim(),
             attendeeEmail,
             attendeeName,
             price
           });
         } catch (err) {
           logger.error({ err }, 'Failed to extract ticket details from order-ticket');
         }
       }

       // If no ticket details found, try to extract from table rows
       if (ticketDetails.length === 0) {
         try {
           const tableRows = await this.page.locator('table tr').all();
           for (const row of tableRows) {
             const cells = await row.locator('td').all();
             if (cells.length >= 4) {
               // Extract ticket type from first cell
               const ticketType = await cells[0].textContent() || '';
               const quantity = await cells[1].textContent() || '';
               const unitPrice = await cells[2].textContent() || '';
               const totalPrice = await cells[3].textContent() || '';
               
               // Skip header rows or empty rows
               if (ticketType.trim() && !ticketType.toLowerCase().includes('ticket') && !ticketType.toLowerCase().includes('total')) {
                 ticketDetails.push({
                   ticketCode: '', // Not available in table format
                   ticketType: ticketType.trim(),
                   attendeeEmail: customerEmail, // Use customer email as fallback
                   attendeeName: customerName || '',
                   price: totalPrice.trim()
                 });
               }
             }
           }
         } catch (err) {
           logger.error({ err }, 'Failed to extract ticket details from table');
         }
       }

      return {
        customerEmail,
        customerName,
        customerPhone,
        discountCode,
        ticketDetails,
        ticketCount: ticketDetails.length
      };

    } catch (err) {
      logger.error({ err, orderId }, 'Failed to get order details');
      return null;
    }
  }

  /**
   * Get detailed information about a discount code
   */
  async getCodeDetails(eventId: string, code: string): Promise<CodeDetails | null> {
    try {
      // Navigate to the discount edit page
      const discountsUrl = `${this.baseUrl}/my/events/${eventId}/discounts`;
      await this.page.goto(`${discountsUrl}?search=${encodeURIComponent(code)}`);
      await this.page.waitForLoadState('networkidle');

      // Click on the code to go to edit page
      const codeLink = this.page.locator(`a.btn-code:has-text("${code}")`).first();
      if (!(await codeLink.count())) {
        logger.warn({ code }, 'Code link not found');
        return null;
      }

      await codeLink.click();
      await this.page.waitForLoadState('networkidle');

      // Extract code details from the edit form
      const codeValue = await this.page.locator('input#code').inputValue().catch(() => code);
      const discountAmount = await this.page.locator('input#amount').inputValue().catch(() => '0');
      
      // Check if it's percentage or amount - look for the dropdown toggle button
      const unitButtonText = await this.page.locator('button.dropdown-toggle.type, button#type-1').first().textContent().catch(() => '%');
      const unitText = unitButtonText ?? '%';
      const discountType: 'percentage' | 'amount' = unitText.includes('%') ? 'percentage' : 'amount';

      // Get limits
      const orderLimit = parseInt(await this.page.locator('input#usage_limit, input[name="usage_limit"]').inputValue().catch(() => '0'));
      const ticketLimit = parseInt(await this.page.locator('input#ticket_limit, input[name="ticket_limit"]').inputValue().catch(() => '0'));

      // Get usage from the form labels
      const orderUsageRaw = await this.page.locator('text=/0 used/').first().textContent().catch(() => '0 used');
      const orderUsageText = orderUsageRaw ?? '0 used';
      const ordersUsed = parseInt((orderUsageText.match(/(\d+)\s*used/)?.[1]) || '0');
      const ticketsUsed = ordersUsed; // Usually same for single-use codes

      // Get validity dates if present
      let validFrom: string | undefined;
      let validTo: string | undefined;
      try {
        const fromInput = await this.page.locator('input[type="date"]').first().inputValue();
        const toInput = await this.page.locator('input[type="date"]').nth(1).inputValue();
        validFrom = fromInput || undefined;
        validTo = toInput || undefined;
      } catch {}

      // Get ticket types from the dropdown
      const ticketTypes: string[] = [];
      try {
        // Check the dropdown button text first
        const dropdownButton = this.page.locator('button[data-id="applies_to_ticket_types"]').first();
        const buttonText = await dropdownButton.textContent() || '';
        
        if (buttonText.includes('All ticket types')) {
          ticketTypes.push('All ticket types');
        } else {
          // Click to open dropdown and get selected options
          await dropdownButton.click();
          await this.page.waitForTimeout(500); // Wait for dropdown to open
          
          // Get all available ticket types from dropdown
          const options = await this.page.locator('.dropdown-menu .dropdown-item .text').all();
          for (const option of options) {
            const text = await option.textContent();
            if (text) {
              // Extract just the ticket type name (before price)
              const ticketType = text.split('(')[0].trim();
              ticketTypes.push(ticketType);
            }
          }
          
          // Close dropdown by clicking elsewhere
          await this.page.locator('body').click();
        }
      } catch (err) {
        logger.debug({ err, code }, 'Could not extract ticket types');
        ticketTypes.push('Unknown');
      }

      // Get description from the title field
      const description = await this.page.locator('input[name="title"], input#title').inputValue().catch(() => '');

      // Check if temporarily disabled (look for toggle or checkbox)
      const isTemporarilyDisabled = await this.page.locator('input[type="checkbox"]:has-text("temporarily disabled"), .toggle-switch input').isChecked().catch(() => false);

      return {
        code: codeValue,
        discount: discountAmount + (discountType === 'percentage' ? '%' : ` €`),
        discountType,
        orderLimit,
        ticketLimit,
        ordersUsed,
        ticketsUsed,
        validFrom,
        validTo,
        ticketTypes,
        description,
        isTemporarilyDisabled
      };

    } catch (err) {
      logger.error({ err, code }, 'Failed to get code details');
      return null;
    }
  }

  /**
   * Scrape all codes with their usage data - optimized version
   */
  async getAllCodesWithUsage(eventId: string, includeOrderDetails = false): Promise<CodeUsageData[]> {
    const results: CodeUsageData[] = [];
    
    try {
      const discountsUrl = `${this.baseUrl}/my/events/${eventId}/discounts`;
      let currentPage = 1;
      let hasMorePages = true;

      while (hasMorePages) {
        const pageUrl = currentPage === 1 ? discountsUrl : `${discountsUrl}?page=${currentPage}`;
        await this.page.goto(pageUrl);
        await this.page.waitForLoadState('networkidle');

        // Extract all code data from the page in one go using page.evaluate
        const pageData = await this.page.evaluate(() => {
          const codeRows: Array<{code: string, usageText: string, editUrl: string}> = [];
          
          // Find all rows with discount codes
          const rows = document.querySelectorAll('tr');
          
          for (const row of rows) {
            const button = row.querySelector('button[data-code]');
            const editLink = row.querySelector('a[href*="/discounts/"][href*="/edit"]');
            const usageCell = row.querySelector('td:nth-child(3)');
            
            if (button && editLink && usageCell) {
              const code = button.getAttribute('data-code');
              const editUrl = editLink.getAttribute('href');
              const usageText = usageCell.textContent || '';
              
              if (code && editUrl) {
                codeRows.push({
                  code,
                  usageText: usageText.replace(/\s+/g, ' ').trim(),
                  editUrl
                });
              }
            }
          }
          
          return codeRows;
        });
        
        if (pageData.length === 0) {
          hasMorePages = false;
          break;
        }

        // Process each code
        for (const { code, usageText, editUrl } of pageData) {
          logger.info({ code, page: currentPage }, 'Processing code data');
          
          if (includeOrderDetails) {
            // For detailed scraping, use the optimized method
            const usageData = await this.getCodeUsageDataOptimized(eventId, code, editUrl, usageText);
            if (usageData) results.push(usageData);
          } else {
            // Parse usage from the already extracted text
            const patterns = [
              /(\d+)\s*\/\s*(\d+)\s*orders.*?(\d+)\s*\/\s*(\d+)\s*tickets/,
              /(\d+)\s*\/\s*(\d+)\s*order.*?(\d+)\s*\/\s*(\d+)\s*ticket/,
              /(\d+)\s*orders.*?(\d+)\s*\/\s*(\d+)\s*tickets/,
              /(\d+)\s*\/\s*(\d+).*?(\d+)\s*\/\s*(\d+)/
            ];
            
            let usageMatch = null;
            for (const pattern of patterns) {
              usageMatch = usageText.match(pattern);
              if (usageMatch) break;
            }
            
            if (usageMatch) {
              results.push({
                code,
                ordersUsed: parseInt(usageMatch[1]),
                orderLimit: parseInt(usageMatch[2]),
                ticketsUsed: parseInt(usageMatch[3]),
                ticketLimit: parseInt(usageMatch[4]),
                orders: []
              });
            } else {
              // If no pattern matches, at least record the code
              logger.warn({ code, usageText }, 'Could not parse usage text');
              results.push({
                code,
                ordersUsed: 0,
                orderLimit: 0,
                ticketsUsed: 0,
                ticketLimit: 0,
                orders: []
              });
            }
          }
        }

        // Check if there's a next page
        const nextPageLink = await this.page.locator('a[href*="page="]:has-text("Next"), a[href*="page="]:has-text("»")').count();
        if (nextPageLink === 0) {
          hasMorePages = false;
        } else {
          currentPage++;
        }
      }

      logger.info({ totalCodes: results.length }, 'Completed scraping all codes');
      return results;

    } catch (err) {
      logger.error({ err }, 'Failed to scrape all codes');
      return results;
    }
  }

  /**
   * Optimized version that uses direct URL navigation instead of searching
   */
  private async getCodeUsageDataOptimized(eventId: string, code: string, editUrl: string, usageText: string): Promise<CodeUsageData | null> {
    try {
      // Parse basic usage from the already extracted text
      const patterns = [
        /(\d+)\s*\/\s*(\d+)\s*orders.*?(\d+)\s*\/\s*(\d+)\s*tickets/,
        /(\d+)\s*\/\s*(\d+)\s*order.*?(\d+)\s*\/\s*(\d+)\s*ticket/
      ];
      
      let ordersUsed = 0, orderLimit = 0, ticketsUsed = 0, ticketLimit = 0;
      for (const pattern of patterns) {
        const match = usageText.match(pattern);
        if (match) {
          ordersUsed = parseInt(match[1]);
          orderLimit = parseInt(match[2]);
          ticketsUsed = parseInt(match[3]);
          ticketLimit = parseInt(match[4]);
          break;
        }
      }

      // Extract discount ID from edit URL
      const discountIdMatch = editUrl.match(/\/discounts\/(\d+)\/edit/);
      const discountId = discountIdMatch ? discountIdMatch[1] : null;

      // If code is used, get order details
      const orders: OrderInfo[] = [];
      if (ordersUsed > 0 && discountId) {
        // Navigate to orders filtered by this discount code
        const ordersUrl = `${this.baseUrl}/my/events/${eventId}/orders?discount=${discountId}`;
        await this.page.goto(ordersUrl);
        await this.page.waitForLoadState('networkidle');

        // Extract order data in one go
        const orderData = await this.page.evaluate(() => {
          const orderRows: Array<{
            orderId: string;
            dateText: string;
            contactInfo: string;
            ticketCount: number;
            priceStatus: string;
          }> = [];
          
          const rows = document.querySelectorAll('tbody tr');
          for (const row of rows) {
            const orderLink = row.querySelector('a[href*="/orders/"][href*="/edit"]');
            if (!orderLink) continue;
            
            const href = orderLink.getAttribute('href') || '';
            const orderIdMatch = href.match(/\/orders\/(\d+)\/edit/);
            if (!orderIdMatch) continue;
            
            const cells = row.querySelectorAll('td');
            if (cells.length < 5) continue;
            
            orderRows.push({
              orderId: orderIdMatch[1],
              dateText: cells[1].textContent || '',
              contactInfo: cells[2].textContent || '',
              ticketCount: parseInt(cells[3].textContent || '0'),
              priceStatus: cells[4].textContent || ''
            });
          }
          
          return orderRows;
        });

        // Process each order
        for (const orderInfo of orderData) {
          try {
            // Extract email and phone from contact info
            const emailMatch = orderInfo.contactInfo.match(/([^\s]+@[^\s]+)/);
            const phoneMatch = orderInfo.contactInfo.match(/(\+\d+)/);
            const customerEmail = emailMatch ? emailMatch[1].trim() : '';
            const customerPhone = phoneMatch ? phoneMatch[1].trim() : '';

            // Extract price and status
            const priceMatch = orderInfo.priceStatus.match(/([\d.,]+)\s*([€$£])/);
            const totalAmount = priceMatch ? priceMatch[1] : '';
            const currency = priceMatch ? priceMatch[2] : '€';
            const status = orderInfo.priceStatus.includes('Completed') ? 'completed' : 'pending';

            // Get detailed order information if needed
            const orderDetails = await this.getOrderDetails(orderInfo.orderId);
            
            orders.push({
              orderId: orderInfo.orderId,
              orderDate: orderInfo.dateText.trim(),
              customerEmail,
              customerPhone,
              ticketCount: orderInfo.ticketCount,
              totalAmount,
              currency,
              status,
              discountCode: code,
              ticketDetails: orderDetails?.ticketDetails || [],
              customerName: orderDetails?.customerName || ''
            });
          } catch (err) {
            logger.error({ err, orderId: orderInfo.orderId }, 'Failed to process order');
          }
        }
      }

      return {
        code,
        ordersUsed,
        orderLimit,
        ticketsUsed,
        ticketLimit,
        orders,
        discountId,  // Include Fienta discount ID
        editUrl      // Include edit URL
      };

    } catch (err) {
      logger.error({ err, code }, 'Failed to get optimized code usage data');
      return null;
    }
  }

  /**
   * Lightweight but smart: Get codes list and capture essential metadata during pagination
   */
  async getCodesList(eventId: string): Promise<{ codes: string[], metadata: Record<string, { discountId: string, editUrl: string }> }> {
    const codes: string[] = [];
    const metadata: Record<string, { discountId: string, editUrl: string }> = {};
    
    try {
      const discountsUrl = `${this.baseUrl}/my/events/${eventId}/discounts`;
      let currentPage = 1;
      let hasMorePages = true;
      
      while (hasMorePages) {
        logger.info({ currentPage }, 'Scanning codes page (with smart metadata capture)');
        
        await this.page.goto(`${discountsUrl}?page=${currentPage}`);
        await this.page.waitForLoadState('networkidle');
        
        // Get all code rows on this page
        const codeRows = await this.page.locator('tbody tr').all();
        
        if (codeRows.length === 0) {
          hasMorePages = false;
          break;
        }
        
        for (const row of codeRows) {
          try {
            // Get code name from the button
            const codeButton = row.locator('button[data-code]');
            const code = await codeButton.getAttribute('data-code');
            
            if (code) {
              codes.push(code);
              
              // Extract discount ID and edit URL while we're here
              const editButton = row.locator('a[href*="/discounts/"][href*="/edit"]');
              const editUrl = await editButton.getAttribute('href');
              
              if (editUrl) {
                // Extract discount ID from URL: /my/events/118714/discounts/247364/edit
                const urlMatch = editUrl.match(/\/discounts\/(\d+)\/edit/);
                const discountId = urlMatch ? urlMatch[1] : '';
                
                if (discountId) {
                  metadata[code] = {
                    discountId,
                    editUrl: editUrl.startsWith('http') ? editUrl : `${this.baseUrl}${editUrl}`
                  };
                }
              }
            }
          } catch (err) {
            // Skip individual row errors but continue processing
            logger.debug({ err }, 'Error processing code row');
          }
        }
        
        // Check if there's a next page
        const nextPageLink = this.page.locator('a[aria-label="Next page"]');
        hasMorePages = await nextPageLink.count() > 0 && !(await nextPageLink.isDisabled());
        currentPage++;
      }
      
      logger.info({ 
        totalCodes: codes.length, 
        metadataCaptured: Object.keys(metadata).length,
        metadataPercentage: Math.round((Object.keys(metadata).length / codes.length) * 100)
      }, 'Smart codes list completed');
      
      return { codes, metadata };
      
    } catch (err) {
      logger.error({ err, eventId }, 'Failed to get codes list');
      return { codes, metadata }; // Return partial results
    }
  }
}

// Export enhanced FientaClient that includes the new scraping methods
export { FientaEnhancedScraper as EnhancedScraper };
